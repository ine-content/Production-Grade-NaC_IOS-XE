# TODO 10 — Verify Live State with nac-test

## Topics Covered

```
✓ Why a clean plan doesn't prove the network works
✓ How nac-test and Jinja turn the data model into tests
✓ Reading live router state over RESTCONF
✓ Checking what a plan can't see: whether OSPF neighbors are really up
✓ Reading a finished test template, line by line
✓ Tests that follow the data: change the data and the tests change
✓ Catching a real problem that terraform plan reports as fine
```

## Recap

This folder already has TODO 09 solved, including `drift_check.sh`. Terraform can tell you that a router's configuration matches the data model. But a matching config doesn't prove the network works. An OSPF neighbor can drop while the configuration still matches your data exactly. A plan can't see that, because it only compares configuration. In this TODO, you run tests that ask the routers what they're doing right now, including whether their OSPF neighbors are up. The test template is already written and sits in `tests/`. You read it, run it, and watch it catch a problem that `terraform plan` calls fine.

## Scenario

In TODO 09, Terraform told you whether a router's configuration matched your data. That check reads configuration. It doesn't ask the router what it's doing right now. In this TODO, you test the live routers directly.

Here's how it works. The folder has a test template, which is a test file with blanks that get filled in from your data model. A tool called `nac-test` fills in the blanks (this is called rendering) and hands the result to Robot Framework, which runs the tests. The template loops over your data, so one template becomes many tests. If you add a fourth router to your YAML, nac-test makes a fourth hostname test automatically. You don't edit the template.

Each test asks a router a question over RESTCONF. That's the HTTPS interface of IOS-XE. A RESTCONF request is a normal web request to an address like `https://10.10.10.10/restconf/data/...`, and the router answers with JSON. Terraform used NETCONF in the earlier TODOs. RESTCONF is a different way into the same router, and it's easier to call from a test.

The template makes three kinds of test:

- **Hostname:** for each router, ask for its hostname and check that it matches the data.
- **Loopback:** for each loopback in the data, ask the router for that loopback and check that it has the right address.
- **OSPF neighbor:** for each router, and for each other router that runs OSPF, ask the router for its live OSPF neighbor table and check that the other router is listed in state FULL. FULL means the two routers have finished exchanging their routing information.

The data has three routers. Each has Loopback0 and Loopback10, and each has two OSPF neighbors. So that makes 15 tests: three hostname tests, six loopback tests, and six OSPF neighbor tests.

The third kind is the reason this tool exists. A plan compares configuration with your data. Whether an OSPF neighbor is up isn't configuration. It's what the routers are doing right now. If someone changes a setting that Terraform doesn't manage, the plan says nothing, and the network can still break. You'll see exactly that in step 10. You'll break OSPF on R12, `terraform plan` will report no changes, and the tests will fail.

One thing needs doing on the routers first. RESTCONF is off until you turn it on, so step 3 enables it. Nothing else on the routers changes, and Terraform doesn't manage this setting.

## Worked Example

Here's a made-up router, `EDGE1`, and a template that makes one test for each router in the data. First, the data:

```yaml
iosxe:
  devices:
    - name: EDGE1
      host: 192.0.2.1
      configuration:
        system:
          hostname: EDGE1
```

The template, `tests/example.robot`:

```
*** Test Cases ***
{% for device in iosxe.devices | default([]) %}
{{ device.name }} is in the data
    Log    {{ device.name }} lives at {{ device.host }}
{% endfor %}
```

After `nac-test` renders it, the Robot file that actually runs is:

```
*** Test Cases ***
EDGE1 is in the data
    Log    EDGE1 lives at 192.0.2.1
```

Things to notice:

- `{% ... %}` is a Jinja instruction, here a loop. `{{ ... }}` is a Jinja value to print. Both are used up during rendering, so they never reach Robot.
- `${ ... }` is a Robot variable. It's left alone during rendering and filled in when the test runs. So `{{ }}` is for data you already have, and `${ }` is for things you only learn from the router.
- `iosxe` is the top key in your YAML. Everything under it is reachable with dots, like `device.configuration.system.hostname`.
- Add a second router to the data and a second test appears. Nobody edits the template.
- Robot separates a keyword from its arguments with at least two spaces. One space isn't enough.

## Technical Requirements

The file `tests/verify_routers.robot` is already in this folder. You don't edit it. nac-test renders it from the merged data, and it makes these tests:

| Test name | Where | Router path asked (after `/restconf/data/`) | Pass when |
|-----------|-------|---------------------------------------------|-----------|
| `<router> hostname` | each device | `Cisco-IOS-XE-native:native/hostname` | the answer equals `configuration.system.hostname` |
| `<router> Loopback<id>` | each loopback of each device | `Cisco-IOS-XE-native:native/interface/Loopback=<id>` | the answer contains the loopback's `ipv4.address` |
| `<router> OSPF neighbor <router-id>` | each device that runs OSPF, once for every other device that runs OSPF | `Cisco-IOS-XE-ospf-oper:ospf-oper-data/ospf-state` | the neighbor table has an entry whose `neighbor-id` is the other router's OSPF `router_id`, and its state is FULL |

Every request goes over HTTPS to the device's `host` from the data model. The router's certificate is self-signed, so the tests don't verify it. The login comes from the terminal's environment (`%{IOSXE_USERNAME}` and `%{IOSXE_PASSWORD}` in Robot), and no credentials appear in the file. The tests never change anything on a router.

What you do in this TODO: turn on RESTCONF, read the template, render it, run it, change the data to see the tests follow, and break OSPF on a router to see tests fail while `terraform plan` stays quiet.

## The Provided Template

Open `tests/verify_routers.robot` and follow along. It has four parts.

**Part 1: Settings.** These two lines are a label and a library.

```
*** Settings ***
Documentation     The live routers match the data model
Library           RequestsLibrary
```

`Documentation` is only a note. `Library RequestsLibrary` loads the Robot library that sends web requests.

**Part 2: the `Router Get` keyword.** A keyword is a reusable action, like a function. This one takes a router address and a path, asks the router, and gives back the answer.

```
Router Get
    [Documentation]    GET one RESTCONF path from a router and return the data under its top-level key.
    [Arguments]    ${host}    ${path}
    ${auth}=    Create List    %{IOSXE_USERNAME}    %{IOSXE_PASSWORD}
    Create Session    ${host}    https://${host}    auth=${auth}    verify=${FALSE}
    ${headers}=    Create Dictionary    Accept=application/yang-data+json
    ${response}=    GET On Session    ${host}    /restconf/data/${path}    headers=${headers}    expected_status=200
    ${data}=    Evaluate    next(iter($response.json().values()))
    RETURN    ${data}
```

- `[Documentation]` is a note about what the keyword does.
- `[Arguments]` names the two inputs: `${host}` and `${path}`.
- `Create List ... %{IOSXE_USERNAME} %{IOSXE_PASSWORD}` builds the login. `%{ }` reads an environment variable, so no password is typed in the file.
- `Create Session` opens an HTTPS connection to the router. `verify=${FALSE}` skips the certificate check because the certificate is self-signed.
- `Create Dictionary Accept=...` asks the router to answer in JSON.
- `GET On Session` sends the request. `expected_status=200` fails the test if the router answers with anything else.
- `Evaluate next(iter(...))` takes the value under the answer's one top key. For example, `{"Cisco-IOS-XE-native:hostname":"R10"}` becomes `R10`.
- `RETURN` hands that value back to the test.

**Part 3: the `Neighbor Should Be Full` keyword.** This keyword looks through a router's OSPF data for one neighbor and fails unless that neighbor is in state FULL.

```
Neighbor Should Be Full
    [Documentation]    Fail unless the OSPF data shows this neighbor router ID in state FULL.
    [Arguments]    ${state}    ${neighbor_id}
    ${objects}=    Evaluate    (lambda walk, data: walk(walk, data))(lambda walk, x: ([x] if isinstance(x, dict) else []) + [y for v in (list(x.values()) if isinstance(x, dict) else x if isinstance(x, list) else []) for y in walk(walk, v)], $state)
    ${states}=    Evaluate    [str(o.get('state')) for o in $objects if o.get('neighbor-id') == '${neighbor_id}']
    Should Not Be Empty    ${states}    No OSPF neighbor ${neighbor_id} in the neighbor table
    ${full}=    Evaluate    any('full' in s.lower() for s in $states)
    Should Be True    ${full}    Neighbor ${neighbor_id} is not FULL. States seen: ${states}
```

- `[Arguments]` names the two inputs: `${state}` is the router's OSPF data, and `${neighbor_id}` is the router ID of the neighbor we expect to see.
- The first `Evaluate` is one line of Python that walks through the whole answer and collects every entry in it, however deeply it's nested. The OSPF answer is nested several levels (instance, area, interface, neighbor), so this way the test doesn't depend on the exact nesting. You don't have to read the lambda. Think of it as a "find every entry" loop.
- The second `Evaluate` keeps only the entries whose `neighbor-id` is the router ID we expect, and collects their `state` values.
- `Should Not Be Empty` fails with "No OSPF neighbor ... in the neighbor table" if the router doesn't list that neighbor at all.
- The third `Evaluate` is true if any of those states contains the word "full". The router reports FULL as `ospf-nbr-full`, so this matches it.
- `Should Be True` fails with "Neighbor ... is not FULL" and shows the states it saw. A neighbor stuck in INIT or EXSTART fails here.

**Part 4: the test cases.** This is where the data model comes in. Lines that start with `{%` and text in `{{ }}` are Jinja. They're filled in during rendering, before Robot runs.

```
*** Test Cases ***
{% for device in iosxe.devices | default([]) %}
{{ device.name }} hostname
    [Tags]    iosxe    system
    ${hostname}=    Router Get    {{ device.host }}    Cisco-IOS-XE-native:native/hostname
    Should Be Equal    ${hostname}    {{ device.configuration.system.hostname }}

{% for loopback in device.configuration.interfaces.loopbacks | default([]) %}
{{ device.name }} Loopback{{ loopback.id }}
    [Tags]    iosxe    interfaces
    ${entries}=    Router Get    {{ device.host }}    Cisco-IOS-XE-native:native/interface/Loopback={{ loopback.id }}
    ${text}=    Convert To String    ${entries}[0]
    Should Contain    ${text}    {{ loopback.ipv4.address }}

{% endfor %}
{% set my_processes = (device.configuration.routing | default({})).ospf_processes | default([]) %}
{% if my_processes | length > 0 %}
{% for other in iosxe.devices | default([]) %}
{% set other_processes = (other.configuration.routing | default({})).ospf_processes | default([]) %}
{% if other.name != device.name and other_processes | length > 0 %}
{{ device.name }} OSPF neighbor {{ other_processes[0].router_id }}
    [Tags]    iosxe    ospf    operational
    ${state}=    Router Get    {{ device.host }}    Cisco-IOS-XE-ospf-oper:ospf-oper-data/ospf-state
    Neighbor Should Be Full    ${state}    {{ other_processes[0].router_id }}

{% endif %}
{% endfor %}
{% endif %}
{% endfor %}
```

- The outer `{% for device ... %}` repeats everything below it once for each router in the data.
- `{{ device.name }} hostname` is the test name, for example `R10 hostname`.
- `[Tags]` puts labels on the test, so reports can be filtered.
- `Router Get {{ device.host }} ...hostname` asks that router, at its management address, for its hostname.
- `Should Be Equal` passes only if the answer equals the hostname in the data.
- The inner `{% for loopback ... %}` repeats the next block once for each loopback of that router.
- `{{ device.name }} Loopback{{ loopback.id }}` is the loopback test name, for example `R10 Loopback0`.
- The loopback request asks for `interface/Loopback=<id>`. The router answers with a list of entries.
- `Convert To String ${entries}[0]` turns the first entry into text.
- `Should Contain` passes only if that text contains the address from the data.
- The first `{% endfor %}` closes the loopback loop. The OSPF tests come next, still inside the router loop.
- `{% set my_processes = ... %}` saves a value in a Jinja variable. Here it's the list of OSPF processes on this router, or an empty list if it has none. The two `default` filters keep the template from failing on a router that has no `routing` section.
- `{% if my_processes | length > 0 %}` skips routers that don't run OSPF.
- The inner `{% for other ... %}` loops over every router again, to find this router's neighbors. `other.name != device.name` skips the router itself, and the second `{% set %}` and `{% if %}` skip routers without OSPF.
- `{{ device.name }} OSPF neighbor {{ other_processes[0].router_id }}` is the test name, for example `R10 OSPF neighbor 10.255.0.11`. The `[0]` means the first OSPF process of the other router, and `router_id` is its OSPF router ID.
- The OSPF request asks for `Cisco-IOS-XE-ospf-oper:ospf-oper-data/ospf-state`. The "oper" in the name means operational data: what the router is doing right now, not what's configured.
- `Neighbor Should Be Full ${state} ...` hands that answer and the other router's ID to the keyword from Part 3.
- The last `{% endfor %}` lines close the remaining loops.

## Working Folder

Do everything for this TODO from its own folder. Open a terminal and run:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-10-Verify-Live-State-with-nac-test
```

Change the path if you put the course folder somewhere else.

## Before You Start

You can do each TODO on its own, so this one assumes the routers already have the work from TODO 06 to 08. TODO 09 adds no router configuration.

Here is how to check R10:

     show ip ospf neighbor
     show running-config interface Loopback10

You should see two neighbors in state FULL, and Loopback10 with the description BRANCH-LAN and R10's address 172.16.10.1, mask 255.255.255.255.

Even if the routers already look like that, start with a baseline apply. This folder already has the solved data and main.tf for everything before this TODO. The apply does two jobs. It gives Terraform a record of the earlier work, so later plans only show this TODO's changes. And it catches up any router that's behind, like a new router, a reset one, or a restored snapshot. If a router already has the work, the apply just matches it. On CWS, in this folder, set the router login:

     export IOSXE_USERNAME=<your username>
     read -s IOSXE_PASSWORD; export IOSXE_PASSWORD

Then run:

     terraform init
     terraform plan
     terraform apply

The plan lists what the earlier TODOs configured. Read it and type yes. Then run write memory on R10, R11, and R12 so they keep the config after a reload.

When it finishes, run the check commands again and make sure the output looks right.

## Steps

Each step starts by saying where to run it. "On CWS" means a normal terminal on the lab machine (CWS), in this folder. "On R10" (or R11, R12) means that router's own command line (SSH or console). These labels are only directions. You don't type them anywhere.

```
1. On CWS: Check that nac-test is installed:

     nac-test --version

   It prints a version number, 2.0.0 or higher. If the command isn't
   found, install the course packages again as described in
   OFFLINE-SETUP.md.

2. On R10, R11, and R12: Take a snapshot on each router, then check it:

     copy running-config flash:before-todo10.cfg
     dir flash:before-todo10.cfg

   Press Enter to accept the file name. Use bootflash: if flash: isn't
   accepted. The listing must show a size above zero.

3. On R10, R11, and R12: Turn on RESTCONF. First look at what is already
   there:

     show running-config | include ip http|restconf

   Then enter:

     configure terminal
      ip http secure-server
      ip http authentication local
      restconf
     end

   If a line was already in the output, entering it again changes
   nothing. Write down which of the three were missing, because the
   reset section at the end needs it.

   RESTCONF is only in the running configuration until you save it, so
   a reload would turn it off again. On R10, R11, and R12: Save it:

     write memory

4. On CWS: Ask each router for its hostname the way a test will. This
   uses the router login you set in Before You Start.

   Then run:

     for h in 10.10.10.10 10.10.10.11 10.10.10.12; do
       curl -sk -u "$IOSXE_USERNAME:$IOSXE_PASSWORD" \
         -H 'Accept: application/yang-data+json' \
         https://$h/restconf/data/Cisco-IOS-XE-native:native/hostname
       echo
     done

   You should get one line of JSON per router, shown in What You Should
   See below. If a router doesn't answer, wait half a minute and try
   again. Don't go on until all three do.

5. On CWS: Read the template. Open tests/verify_routers.robot in your
   editor, or print it:

     cat tests/verify_routers.robot

   Match each part with The Provided Template above. Don't change it.

6. On CWS: Render the tests without running them, then look at the
   result:

     nac-test -d data -t tests -o test-results --render-only
     grep -E '^R1[0-2] ' test-results/robot_results/verify_routers.robot

   You should see the 15 test names, listed in What You Should See.

7. On CWS: Check the template without touching a router. A Robot dry
   run walks through every keyword and sends no request:

     nac-test -d data -t tests -o test-results --dry-run

   It must end with: All tests passed: 15 out of 15 tests

8. On CWS: Run the tests against the routers:

     nac-test -d data -t tests -o test-results

   Wait for the summary. All 15 must pass.

9. On CWS: Prove the tests really come from the data. Give R12 a
   different management address for a moment, render, and count where
   the new address shows up:

     sed -i.bak 's/host: 10.10.10.12/host: 10.10.10.99/' data/devices.nac.yaml
     nac-test -d data -t tests -o test-results --render-only
     grep -c '10.10.10.99' test-results/robot_results/verify_routers.robot
     mv data/devices.nac.yaml.bak data/devices.nac.yaml
     nac-test -d data -t tests -o test-results --render-only

   The count must be 5, one line for each of R12's own five tests: its
   hostname, its two loopbacks, and its two OSPF neighbor tests. The
   other routers' tests about R12 don't change, because they ask their
   own router. You never touched the template. The last command renders
   again with your real data.

10. On R12: Break something that Terraform doesn't manage. Change the
    OSPF hello timer on R12's management interface. GigabitEthernet1
    isn't in the data model, so Terraform never looks at it:

     configure terminal
      interface GigabitEthernet1
       ip ospf hello-interval 1
     end

    The OSPF timers on R12 no longer match the other routers, so R12 and
    its neighbors drop each other. Wait about 45 seconds. R10 and R11
    give up on R12 after their 40-second dead timer.

    On CWS: Ask Terraform what it thinks:

     terraform plan -detailed-exitcode
     echo $?

    It must exit 0, which means no changes. Terraform has no idea
    anything is wrong, because the hello timer isn't part of your data.

    Now run the tests:

     nac-test -d data -t tests -o test-results
     echo $?

    Exactly 4 tests must fail. They are R12 OSPF neighbor 10.255.0.10,
    R12 OSPF neighbor 10.255.0.11, R10 OSPF neighbor 10.255.0.12, and
    R11 OSPF neighbor 10.255.0.12. The other 11 pass, and the exit code
    is 4. The plan said everything was fine, and the tests caught the
    problem.

    Now fix it. On R12:

     configure terminal
      interface GigabitEthernet1
       no ip ospf hello-interval
     end

    On R12: Wait about 40 seconds, until both neighbors are FULL again:

     show ip ospf neighbor

    On CWS: Run the tests again. All 15 must pass.

11. On CWS: Run: python grading.py
```

## What You Should See

Step 4 should print one line per router:

```
{"Cisco-IOS-XE-native:hostname":"R10"}
{"Cisco-IOS-XE-native:hostname":"R11"}
{"Cisco-IOS-XE-native:hostname":"R12"}
```

After step 6, the names of the 15 tests are:

```
R10 hostname
R10 Loopback0
R10 Loopback10
R10 OSPF neighbor 10.255.0.11
R10 OSPF neighbor 10.255.0.12
R11 hostname
R11 Loopback0
R11 Loopback10
R11 OSPF neighbor 10.255.0.10
R11 OSPF neighbor 10.255.0.12
R12 hostname
R12 Loopback0
R12 Loopback10
R12 OSPF neighbor 10.255.0.10
R12 OSPF neighbor 10.255.0.11
```

If step 7 reports a keyword or a syntax problem, you changed the template. Put it back the way it was.

A live run that passes (step 8) ends like this. The times differ:

```
15 tests, 15 passed, 0 failed, 0 skipped.
```

In step 10, after you add the hello timer on R12, the plan exits `0` and the live run fails 4 tests:

```
15 tests, 11 passed, 4 failed, 0 skipped.
```

The failure messages say either that the neighbor is missing from the router's neighbor table, or that it isn't FULL. For example: `No OSPF neighbor 10.255.0.10 in the neighbor table`. The exit code is the number of failed tests, so `4`. Terraform's plan said nothing about this problem. Only the tests did.

## Put a router back

To undo this TODO, remove only the lines that were missing in step 3. If all three were missing, enter this on each router:

```
configure terminal
 no restconf
 no ip http authentication local
 no ip http secure-server
end
```

Leave out any line that was already in the configuration before step 3, because something else may depend on it. Leave OSPF and the rest alone. The snapshot from step 2 can also put a router back in one command with `configure replace flash:before-todo10.cfg`. It replaces the whole running configuration, so use it only if nothing else changed on that router since the snapshot.

If step 10 didn't finish and R12 still has the hello timer, remove it. On R12:

```
configure terminal
 interface GigabitEthernet1
  no ip ospf hello-interval
end
```

Then wait about 40 seconds and check that `show ip ospf neighbor` shows both neighbors as FULL.

Terraform isn't involved, so `terraform plan` isn't affected either way.

**Save the reset too.** The reset commands change only the running configuration. Run `write memory` on every router you reset. Without it, a reload brings this TODO's settings back from the startup configuration.

## Grading Check

```
python grading.py
```

Run it in the terminal where you exported `IOSXE_USERNAME` and `IOSXE_PASSWORD`. First the grader re-checks TODO 01 to TODO 09, each against only its own data files. Then it checks that the template still reads the login from the environment and has none typed in. It renders the template with nac-test and compares the 15 tests, names and contents, with what the data says. In a temporary copy it changes the data twice, adding a loopback and moving R12 to a new address, and the rendered tests must change with it. A Robot dry run must pass. Last, it runs the real tests against R10, R11, and R12, and every one must pass. Your real files are never touched, and nothing is changed on a router.

Before you complete this TODO:

```
TODO 10 - Verify Live State with nac-test
────────────────────────────────────────────────────────────────────────────────

[10] Verifying live state with nac-test...

✗ TODO 10 Not Complete

The pipeline cannot continue because the live state is not yet verified by tests generated from the data model.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 10 - Verify Live State with nac-test
────────────────────────────────────────────────────────────────────────────────

[10] Verifying live state with nac-test...
  tests/verify_routers.robot -> rendered by nac-test from the data model
  15 tests: 3 hostname, 6 loopback, 6 OSPF neighbor, all built from the data
  login -> read from IOSXE_USERNAME and IOSXE_PASSWORD, none in the file
  injected: a loopback added to R11 -> a new test appeared
  injected: R12 given another management address -> its tests followed
  robot dry run -> every keyword resolves
  live run -> every test passes on R10, R11 and R12

✓ TODO 10 Complete
The tests are generated from the data model and the live routers pass every one of them.
```

---
