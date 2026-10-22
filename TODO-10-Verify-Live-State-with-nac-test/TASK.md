# TODO 10 — Verify Live State with nac-test

## Topics Covered

```
✓ Why a clean plan doesn't prove the network works
✓ Turning the data model into tests with nac-test and Jinja
✓ Reading live router state over RESTCONF
✓ Checking running state: hostname and loopbacks
✓ Tests that follow the data: change the data and the tests change
```

## Recap

This folder already has TODO 09 solved, including `drift_check.sh`. Terraform can tell you that a router's configuration matches the data model. But a matching config doesn't prove the network works. An interface can be configured exactly as written and still be wrong, for example after a manual change that Terraform hasn't picked up yet. In this TODO, you write tests that ask the routers what they're doing right now.

## Scenario

`nac-test` takes the same data model you've been building and a folder of test templates. It renders the templates with the data, so one template becomes many tests, and then runs them with Robot Framework. Add a router or a loopback to the data, and the tests for it appear without anyone writing them.

The tests talk to each router over RESTCONF, the HTTPS interface of IOS-XE. A RESTCONF request is a normal web request to an address like `https://10.10.10.10/restconf/data/...`, and the router answers with JSON. Terraform used NETCONF in the earlier TODOs. RESTCONF is a different way into the same router, and it's easier to call from a test.

You write one template, `tests/verify_routers.robot`, with two kinds of test. For each router, check the hostname. For each loopback in the data, check that the router has it with the right address. That makes 9 tests for the three routers: three hostname tests and six loopback tests.

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

Create one file, `tests/verify_routers.robot`, that nac-test renders from the merged data. It must make the tests below. Use these exact names so the report is easy to read:

| Test name | Where | Router path asked (after `/restconf/data/`) | Pass when |
|-----------|-------|---------------------------------------------|-----------|
| `<router> hostname` | each device | `Cisco-IOS-XE-native:native/hostname` | the answer equals `configuration.system.hostname` |
| `<router> Loopback<id>` | each loopback of each device | `Cisco-IOS-XE-native:native/interface/Loopback=<id>` | the answer contains the loopback's `ipv4.address` |

Every request goes over HTTPS to the device's `host` from the data model. The router's certificate is self-signed, so the tests don't verify it. The login comes from the terminal's environment (`%{IOSXE_USERNAME}` and `%{IOSXE_PASSWORD}` in Robot), and no credentials may appear in the file. The tests never change anything on a router.

## Notation Used Below

Skeletons in the Steps section use one kind of blank:

```
...   - replace this with your own value or expression.
```

Everything else in a skeleton is already filled in and must stay as it is.

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

   You should get one line of JSON per router, shown in Test It
   Yourself below. If a router doesn't answer, wait half a minute and
   try again. Don't go on until all three do.

5. On CWS: Create tests/verify_routers.robot. Start with this. The
   top part is complete and you copy it as it is. Fill in each ... in
   the test cases:

     *** Settings ***
     Documentation     The live routers match the data model
     Library           RequestsLibrary

     *** Keywords ***
     Router Get
         [Arguments]    ${host}    ${path}
         ${auth}=    Create List    %{IOSXE_USERNAME}    %{IOSXE_PASSWORD}
         Create Session    ${host}    https://${host}    auth=${auth}    verify=${FALSE}
         ${headers}=    Create Dictionary    Accept=application/yang-data+json
         ${response}=    GET On Session    ${host}    /restconf/data/${path}    headers=${headers}    expected_status=200
         ${data}=    Evaluate    next(iter($response.json().values()))
         RETURN    ${data}

     *** Test Cases ***
     {% for device in iosxe.devices | default([]) %}
     ... hostname
         ${hostname}=    Router Get    ...    Cisco-IOS-XE-native:native/hostname
         Should Be Equal    ${hostname}    ...

     {% for loopback in ... | default([]) %}
     ... Loopback...
         ${entries}=    Router Get    ...    Cisco-IOS-XE-native:native/interface/Loopback=...
         ${text}=    Convert To String    ${entries}[0]
         Should Contain    ${text}    ...

     {% endfor %}
     {% endfor %}

   - Every ... is a Jinja value in double curly braces, such as
     {{ device.name }}. The loops use the same dotted names.
   - The loopbacks are under device.configuration.interfaces.loopbacks.
   - The name of a test is the first thing on its line, with no spaces
     in front. It must match the Technical Requirements table exactly.
   - Router Get takes the router's address first, then the path.

6. On CWS: Render the tests without running them, then look at the result:

     nac-test -d data -t tests -o test-results --render-only
     grep -E '^R1[0-2] ' test-results/robot_results/verify_routers.robot

   You should see the 9 test names, listed in Test It Yourself.

7. On CWS: Run them against the routers:

     nac-test -d data -t tests -o test-results

   Wait for the summary. All 9 must pass.

8. On CWS: Run: python grading.py
```

## Test It Yourself (without the grader)

Step 4 should have printed one line per router:

```
{"Cisco-IOS-XE-native:hostname":"R10"}
{"Cisco-IOS-XE-native:hostname":"R11"}
{"Cisco-IOS-XE-native:hostname":"R12"}
```

After step 6, the names of the 9 tests are:

```
R10 hostname
R10 Loopback0
R10 Loopback10
R11 hostname
R11 Loopback0
R11 Loopback10
R12 hostname
R12 Loopback0
R12 Loopback10
```

Check the template without touching a router. A Robot dry run walks through every keyword and reports any it doesn't know, but sends no request:

```
nac-test -d data -t tests -o test-results --dry-run
```

It must end with `All tests passed: 9 out of 9 tests`. If it reports a keyword or a syntax problem, fix the template first.

Check that the tests really come from the data. Give R12 a different management address for a moment, render, and count where the new address shows up:

```
sed -i.bak 's/host: 10.10.10.12/host: 10.10.10.99/' data/devices.nac.yaml
nac-test -d data -t tests -o test-results --render-only
grep -c '10.10.10.99' test-results/robot_results/verify_routers.robot
mv data/devices.nac.yaml.bak data/devices.nac.yaml
```

The count should be `3`, one line for each of R12's three tests. If it's lower, an address was typed into the template instead of coming from the data. Render again after the `mv` so the output folder matches your real data.

A live run that passes ends like this. The times differ:

```
9 tests, 9 passed, 0 failed, 0 skipped.
```

Now break something on a router and see what the tests say. On R12:

```
configure terminal
 interface Loopback10
  ip address 172.16.12.99 255.255.255.255
end
```

Run the tests again:

```
nac-test -d data -t tests -o test-results
echo $?
```

Expect one failure, `R12 Loopback10`. The message under it says the answer from the router doesn't contain `172.16.12.1`. The exit code is the number of failed tests, so `1`. The other 8 still pass. A plan would also notice this one, but only the test says in plain words which check failed. Then put it back on R12:

```
configure terminal
 interface Loopback10
  ip address 172.16.12.1 255.255.255.255
end
```

Run the tests again. They must pass again.

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

Terraform isn't involved, so `terraform plan` isn't affected either way.

**Save the reset too.** The reset commands change only the running configuration. Run `write memory` on every router you reset. Without it, a reload brings this TODO's settings back from the startup configuration.

## Grading Check

```
python grading.py
```

Run it in the terminal where you exported `IOSXE_USERNAME` and `IOSXE_PASSWORD`. First the grader re-checks TODO 01 to TODO 09, each against only its own data files. Then it checks that your template reads the login from the environment and has none typed in. It renders the template with nac-test and compares the 9 tests, names and contents, with what the data says. In a temporary copy it changes the data twice, adding a loopback and moving R12 to a new address, and the rendered tests must change with it. A Robot dry run must pass. Last, it runs the real tests against R10, R11, and R12, and every one must pass. Your real files are never touched, and nothing is changed on a router.

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
  9 tests: 3 hostname and 6 loopback, all built from the data
  login -> read from IOSXE_USERNAME and IOSXE_PASSWORD, none in the file
  injected: a loopback added to R11 -> a new test appeared
  injected: R12 given another management address -> its tests followed
  robot dry run -> every keyword resolves
  live run -> every test passes on R10, R11 and R12

✓ TODO 10 Complete
The tests are generated from the data model and the live routers pass every one of them.
```

---
