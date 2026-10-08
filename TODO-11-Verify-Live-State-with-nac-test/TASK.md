# TODO 11 — Verify Live State with nac-test

## Topics Covered

```
✓ Why a clean plan doesn't prove the network works
✓ Turning the data model into tests with nac-test and Jinja
✓ Reading live router state over RESTCONF
✓ Checking running state: hostname, loopbacks, BGP sessions
✓ Tests that follow the data: change the data and the tests change
```

## Recap

TODO 10 is solved in this folder, including `drift_check.sh`. Terraform can tell you the router's configuration matches the data model. That is not the same as the network working. A BGP neighbor can be configured exactly as written and still be down. In this TODO you write tests that ask the routers what they are doing right now.

## Scenario

`nac-test` takes the same data model you have been building and a folder of test templates. It renders the templates with the data, so one template becomes many tests, and then runs them with Robot Framework. Add a router or a neighbor to the data and the tests for it appear without anyone writing them.

The tests talk to each router over RESTCONF, the HTTPS interface of IOS-XE. A RESTCONF request is a normal web request to an address such as `https://10.10.10.10/restconf/data/...`. The router answers with JSON. Terraform used NETCONF in the earlier TODOs. RESTCONF is a different door into the same router, and it is the easier one to call from a test.

You write one template, `tests/verify_routers.robot`, with three kinds of test. For each router, check the hostname. For each loopback in the data, check that the router has it with the right address. For each BGP neighbor in the data, check that the session is `fsm-established` and the neighbor's AS number is the one in the data. That is 15 tests for the three routers.

One thing needs doing on the routers first. RESTCONF is off until you turn it on, so step 3 enables it. Nothing else on the routers changes, and Terraform doesn't manage it.

## Worked Example

A made-up router, `EDGE1`, and a template that makes one test for each router in the data. The data:

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

- `{% ... %}` is a Jinja instruction, here a loop. `{{ ... }}` is a Jinja value to print. Both are used up while rendering. They never reach Robot.
- `${ ... }` is a Robot variable. It is left alone while rendering and filled in while the test runs. So `{{ }}` is for data you already have, and `${ }` is for things you only learn from the router.
- The name of the data model, `iosxe`, is the top key in your YAML. Everything under it is reachable with dots: `device.configuration.system.hostname`.
- Add a second router to the data and a second test appears. Nobody edits the template.
- Robot separates a keyword from its arguments with at least two spaces. One space is not enough.

## Technical Requirements

One file, `tests/verify_routers.robot`, rendered from the merged data. It makes these tests, and the names must be exactly like this so a report is easy to read:

| Test name | Where | Router path asked (after `/restconf/data/`) | Pass when |
|-----------|-------|---------------------------------------------|-----------|
| `<router> hostname` | each device | `Cisco-IOS-XE-native:native/hostname` | the answer equals `configuration.system.hostname` |
| `<router> Loopback<id>` | each loopback of each device | `Cisco-IOS-XE-native:native/interface/Loopback=<id>` | the answer contains the loopback's `ipv4.address` |
| `<router> BGP neighbor <ip>` | each BGP neighbor of each device | `Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors` | the neighbor `<ip>` is there, its `session-state` is `fsm-established`, and its `as` equals `remote_as` |

Every request goes to the device's `host` from the data model, over HTTPS. The router's certificate is self-signed, so the tests don't verify it. The login comes from the terminal's environment (`%{IOSXE_USERNAME}` and `%{IOSXE_PASSWORD}` in Robot). No credentials may appear in the file. The tests never change anything on a router.

## Notation Used Below

Skeletons in the Steps section use one kind of blank:

```
...   - replace this with your own value or expression.
```

Everything else in a skeleton is already filled in and must stay as it is.

## Working Folder

Do everything for this TODO from its own folder. Open a terminal and run:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-11-Verify-Live-State-with-nac-test
```

Change the path if you put the course folder somewhere else.

## Steps

Each step starts by saying where to run it. "On CWS" means a normal terminal on the lab machine (CWS), in this folder. "On R10" (or R11, R12) means that router's own command line (SSH or console). These labels are only directions. You don't type them anywhere.

```
1. On CWS: Check that nac-test is installed:

     nac-test --version

   It prints a version number, 2.0.0 or higher. If the command isn't
   found, install the course packages again as described in
   OFFLINE-SETUP.md.

2. On R10, R11, R12: Take a snapshot on each router, then check it:

     copy running-config flash:before-todo11.cfg
     dir flash:before-todo11.cfg

   Press Enter to accept the file name. Use bootflash: if flash: isn't
   accepted. The listing must show a size above zero.

3. On R10, R11, R12: Turn on RESTCONF. First look at what is already
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

4. On CWS: Ask each router for its hostname the way a test will. The
   login is still exported in this terminal (IOSXE_USERNAME and
   IOSXE_PASSWORD, as in TODO 06):

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
     {% for neighbor in ... | default([]) %}
     ... BGP neighbor ...
         ${neighbors}=    Router Get    ...    Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors
         ${found}=    Evaluate    [n for n in $neighbors['neighbor'] if n['neighbor-id'] == '...']
         Should Not Be Empty    ${found}    no BGP session to ... on ...
         Should Be Equal    ${found}[0][session-state]    fsm-established
         Should Be Equal As Integers    ${found}[0][as]    ...

     {% endfor %}
     {% endfor %}

   - Every ... is a Jinja value in double curly braces, such as
     {{ device.name }}. The loops use the same dotted names.
   - The loopbacks are under device.configuration.interfaces.loopbacks.
   - The BGP neighbors are under device.configuration.routing.bgp.neighbors.
   - The name of a test is the first thing on its line, with no spaces
     in front. It must match the Technical Requirements table exactly.
   - Router Get takes the router's address first, then the path.

6. On CWS: Render the tests without running them, and look at what you
   got:

     nac-test -d data -t tests -o test-results --render-only
     grep -E '^R1[0-2] ' test-results/robot_results/verify_routers.robot

   You should see the 15 test names, listed in Test It Yourself.

7. On CWS: Run them against the routers:

     nac-test -d data -t tests -o test-results

   Wait for the summary. All 15 must pass.

8. On CWS: Run: python grading.py
```

## Test It Yourself (without the grader)

Step 4 should have printed one line per router:

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
R10 BGP neighbor 10.255.0.11
R10 BGP neighbor 10.255.0.12
R11 hostname
R11 Loopback0
R11 Loopback10
R11 BGP neighbor 10.255.0.10
R11 BGP neighbor 10.255.0.12
R12 hostname
R12 Loopback0
R12 Loopback10
R12 BGP neighbor 10.255.0.10
R12 BGP neighbor 10.255.0.11
```

Check the template without touching a router. A Robot dry run walks through every keyword and reports any it doesn't know, but sends no request:

```
nac-test -d data -t tests -o test-results --dry-run
```

It must end with `All tests passed: 15 out of 15 tests`. If it reports a keyword or a syntax problem, fix the template first.

Check that the tests really come from the data. Give R12 a different management address for a moment, render, and count where the new address shows up:

```
sed -i.bak 's/host: 10.10.10.12/host: 10.10.10.99/' data/devices.nac.yaml
nac-test -d data -t tests -o test-results --render-only
grep -c '10.10.10.99' test-results/robot_results/verify_routers.robot
mv data/devices.nac.yaml.bak data/devices.nac.yaml
```

The count should be `5`, one line for each of R12's five tests. If it is lower, an address was typed into the template instead of coming from the data. Render again after the `mv` so the output folder matches your real data.

A live run that passes ends like this. The times differ:

```
15 tests, 15 passed, 0 failed, 0 skipped.
```

Now break something on a router, which the plan from TODO 10 would not have noticed as a broken network. On R12:

```
configure terminal
 router bgp 65010
  neighbor 10.255.0.10 shutdown
end
```

Wait ten seconds and run the tests again:

```
nac-test -d data -t tests -o test-results
echo $?
```

Expect two failures, because the session is down from both ends: `R12 BGP neighbor 10.255.0.10` and `R10 BGP neighbor 10.255.0.12`. The message under each says the state is not `fsm-established`. The exact word the router reports can differ. The exit code is the number of failed tests, so `2`. The other 13 still pass. Then put it back on R12:

```
configure terminal
 router bgp 65010
  no neighbor 10.255.0.10 shutdown
end
```

Wait about a minute for the session to come up and run the tests again. They must pass again.

## Put a router back

To undo this TODO on the routers, remove only the lines that were missing in step 3. Entered on each router, the full set is:

```
configure terminal
 no restconf
 no ip http authentication local
 no ip http secure-server
end
```

Leave out any line that was already in the configuration before step 3, because something else may depend on it. Leave BGP, OSPF and the rest alone. The snapshot from step 2 can also put a router back in one command with `configure replace flash:before-todo11.cfg`. It replaces the whole running configuration, so use it only if nothing else changed on that router since the snapshot.

Terraform isn't involved, so `terraform plan` is not affected either way.

## Grading Check

```
python grading.py
```

Run it in the terminal where you exported `IOSXE_USERNAME` and `IOSXE_PASSWORD`. The grader re-checks TODO 01 to TODO 10 first, each against only the data files that belong to it. Then it checks that your template reads the login from the environment and has none typed in. It renders the template with nac-test and compares the 15 tests, names and contents, with what the data says. It changes the data three times in a temporary copy, adding a loopback, removing a BGP neighbor and moving R12 to a new address, and the rendered tests must change with it. A Robot dry run must pass. Last, it runs the real tests against R10, R11 and R12, and every one must pass. Your real files are never touched, and nothing is changed on a router.

Before you complete this TODO:

```
TODO 11 - Verify Live State with nac-test
────────────────────────────────────────────────────────────────────────────────

[11] Verifying live state with nac-test...

✗ TODO 11 Not Complete

The pipeline cannot continue because the live state is not yet verified by tests generated from the data model.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 11 - Verify Live State with nac-test
────────────────────────────────────────────────────────────────────────────────

[11] Verifying live state with nac-test...
  tests/verify_routers.robot -> rendered by nac-test from the data model
  15 tests: 3 hostname, 6 loopback, 6 BGP neighbor, all built from the data
  login -> read from IOSXE_USERNAME and IOSXE_PASSWORD, none in the file
  injected: a loopback added to R11 -> a new test appeared
  injected: a BGP neighbor removed from R12 -> its test disappeared
  injected: R12 given another management address -> its tests followed
  robot dry run -> every keyword resolves
  live run -> every test passes on R10, R11 and R12

✓ TODO 11 Complete
The tests are generated from the data model and the live routers pass every one of them.
```

---
