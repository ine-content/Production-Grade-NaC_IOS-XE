# TODO 02 — Layer Shared Settings Across Files

## Topics Covered

```
✓ Splitting one data model across several YAML files
✓ How the files get merged (same device name = combined, key by key)
✓ Writing a shared setting once instead of three times
```

## Recap

TODO 01 is already solved in this folder. `data/devices.nac.yaml` describes the three routers. In this TODO you add a second file for the settings all three routers share.

## Scenario

Say Network Engineering wants every router to use the same domain name. With one big file, someone edits three places. If they miss one, the routers disagree and nobody notices. The fix is layering: what is unique to a device goes in one file, and what is shared goes in another. The tools merge every YAML file in `data/` into a single model, so the result is the same as if you had written it all in one place.

The merge works on device names. Two entries with the same `name` are combined key by key, so the second file only needs the name plus whatever it adds.

## Worked Example

Take a made-up router `EDGE1`, described in one file:

```yaml
# data/devices.nac.yaml
iosxe:
  devices:
    - name: EDGE1
      host: 192.0.2.1
      configuration:
        system:
          hostname: EDGE1
```

A second file adds a setting other routers share:

```yaml
# data/common.nac.yaml
iosxe:
  devices:
    - name: EDGE1
      configuration:
        system:
          mtu: 1500
```

Merged, you get:

```yaml
iosxe:
  devices:
    - name: EDGE1
      host: 192.0.2.1
      configuration:
        system:
          hostname: EDGE1
          mtu: 1500
```

Nothing from the first file is lost, and `mtu` sits next to `hostname` under the same `system`.

## Technical Requirements

All three routers share these settings:

| Setting          | Value          |
|------------------|----------------|
| ip_routing       | true           |
| ip_domain_name   | meridian.local |
| ip_domain_lookup | false          |

## Steps

```
1. Create data/common.nac.yaml.

2. For each of R10, R11 and R12, add an entry with just its name and a
   configuration -> system block holding the three settings from the
   Technical Requirements table.

3. Don't repeat host, hostname or loopbacks here. Those stay in
   data/devices.nac.yaml. And don't copy the shared settings into
   devices.nac.yaml.

4. Save, then run: python grading.py
```

## Test It Yourself (without the grader)

Merge the two files and look at the result:

```
nac-validate data -o merged.yaml
echo $?
cat merged.yaml
```

The exit code should be `0`. In `merged.yaml`, each router should show its own `host`, `hostname` and loopback together with `ip_routing: true`, `ip_domain_name: meridian.local` and `ip_domain_lookup: false`. 

The key order doesn't matter. What matters is that all of it ended up under one device.

Then check that the shared settings are only in the common file (no output means none found):

```
grep -n 'ip_domain' data/devices.nac.yaml
```

Finally, remove `common.nac.yaml` for a moment (`mv data/common.nac.yaml /tmp/`), run the merge again, and see that the shared settings disappear from `merged.yaml`. Put the file back with `mv /tmp/common.nac.yaml data/`.

## Grading Check

```
python grading.py
```

The grader re-checks TODO 01 first. Then it makes sure the shared settings are only in `common.nac.yaml` and that `devices.nac.yaml` has none of them. Last, it merges the two files and checks that every device ends up with its host, hostname, loopback and all three shared settings.

Before you complete this TODO:

```
TODO 02 - Layer Shared Settings Across Files
────────────────────────────────────────────────────────────────────────────────

[2] Layering shared settings across files...

✗ TODO 02 Not Complete

The pipeline cannot continue because the shared settings have not been layered into
their own file correctly yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 02 - Layer Shared Settings Across Files
────────────────────────────────────────────────────────────────────────────────

[2] Layering shared settings across files...
  devices.nac.yaml + common.nac.yaml -> merged into one model
  every device carries ip_routing, ip_domain_name and ip_domain_lookup

✓ TODO 02 Complete
Shared settings live in data/common.nac.yaml and merge cleanly into every device.
```

---
