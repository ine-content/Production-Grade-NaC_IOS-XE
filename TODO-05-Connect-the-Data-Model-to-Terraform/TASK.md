# TODO 05 — Connect the Data Model to Terraform

## Topics Covered

```
✓ What the netascode nac-iosxe Terraform module does
✓ Calling a module: source and inputs
✓ Pointing the module at your data/ folder
✓ terraform init and terraform validate
✓ Why credentials stay out of the .tf files
```

## Recap

TODO 01 to TODO 04 are solved in this folder: the data model, the shared settings, the schema and the two rules. Everything so far ran with plain Python tools. Now you hand the same YAML to Terraform. No router is touched in this TODO.

## Scenario

The YAML says what the network should look like. Something has to turn that into router configuration. That job belongs to the `nac-iosxe` module from the netascode project. It reads your YAML, merges the files the same way you saw in TODO 02, and creates one Terraform resource per piece of configuration: a hostname here, a loopback there.

You don't write any of those resources. Your whole Terraform code is one module call. The module also sets up the `iosxe` provider itself. It builds the list of routers from the `name` and `host` values in your YAML, so the IP addresses live in one place only.

Two things follow from that:

- **No provider block, no host, no password in your `.tf` files.** The provider reads the login from two environment variables, `IOSXE_USERNAME` and `IOSXE_PASSWORD`. You'll set them in TODO 06.
- **`terraform validate` is safe.** It only checks that the code makes sense. It never connects to a router, so it's a good way to test the wiring before anything real is at stake.

## Worked Example

A module call has a name, a `source` that says where the module lives, and inputs. Here is a made-up module that builds VPN settings from files in a `settings/` folder:

```hcl
terraform {
  required_version = ">= 1.5.0"
}

module "lab_vpn" {
  source      = "./modules/vpn"
  config_dirs = ["settings"]
}
```

`source` can be a folder on disk, like here, or a registry address such as `netascode/nac-iosxe/iosxe`. `required_version` stops an older Terraform from running code that needs a newer one.

## Technical Requirements

| Item | Value |
|------|-------|
| Terraform version | 1.9.0 or newer (the module needs it) |
| Module | nac-iosxe, already downloaded to `../offline-bundle/modules/nac-iosxe` |
| Input folder | `data` |
| File to create | `main.tf` |

If your machine has internet and you didn't download the bundle, the module is also on the Terraform registry as `netascode/nac-iosxe/iosxe`, version `1.0.0`. Either source passes the check.

## Notation Used Below

Skeletons in the Steps section use one kind of blank:

```
...   - replace this with your own value or expression.
```

Everything else in a skeleton is already filled in and must stay as it is.

## Steps

```
1. Open a terminal in the course folder and load the lab environment:

     . prep/env.sh

   Then change into this TODO's folder. env.sh puts Terraform on your PATH
   and tells it to read providers from the local mirror.

2. Create main.tf in this folder. Fill in each ... below:

     terraform {
       required_version = "..."
     }

     module "iosxe" {
       source           = "..."
       yaml_directories = [...]
     }

   - required_version: the module needs Terraform 1.9.0 or newer.
   - source: the module folder from the Technical Requirements table.
   - yaml_directories: a list holding the folder with your YAML files.
     The module reads every .yaml and .yml file in it, subfolders
     included, and merges them.

3. Don't add a provider block, a host, a username or a password. The
   module and the environment variables take care of all three.

4. Run:  terraform init
          terraform validate

5. Run: python grading.py
```

## Test It Yourself (without the grader)

Run these from inside this folder, after `. ../prep/env.sh` in your terminal:

```
terraform version
terraform init
terraform validate
terraform providers
grep -niE 'username|password|secret|provider "iosxe"' *.tf
```

What to look for:

- `terraform init` ends with a line like `Terraform has been successfully initialized!`. It also shows the module being picked up and the providers `CiscoDevNet/iosxe`, `netascode/utils` and `hashicorp/local` coming from the mirror.
- `terraform validate` prints `Success! The configuration is valid.`
- `terraform providers` lists the three providers under `module.iosxe`.
- The `grep` prints nothing. Any output means a credential or a provider block slipped into your files.

Now break it on purpose. Misspell one input name, run validate, and put the file back:

```
sed -i.bak 's/yaml_directories/yaml_directorys/' main.tf
terraform validate
mv main.tf.bak main.tf
```

Validate should fail and say that an argument named `yaml_directorys` is not expected. Terraform catches typos in input names before it talks to anything. Run `terraform validate` once more after restoring the file. It should pass again.

## Grading Check

```
python grading.py
```

The grader re-checks TODO 01 to TODO 04 first. Then it reads your `.tf` files. It looks for a `required_version` of 1.9 or newer, a module block that uses `nac-iosxe` as its source and `data` as its input folder, and it makes sure no credential or provider block is anywhere. Last, it runs `terraform init` and `terraform validate`, and both must succeed. Nothing is sent to a router.

Before you complete this TODO:

```
TODO 05 - Connect the Data Model to Terraform
────────────────────────────────────────────────────────────────────────────────

[5] Connecting the data model to Terraform...

✗ TODO 05 Not Complete

The pipeline cannot continue because Terraform is not yet connected to the data
model.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 05 - Connect the Data Model to Terraform
────────────────────────────────────────────────────────────────────────────────

[5] Connecting the data model to Terraform...
  main.tf -> module nac-iosxe reads data/
  no credentials and no provider block in any .tf file
  terraform init -> ok
  terraform validate -> ok

✓ TODO 05 Complete
Terraform loads the nac-iosxe module, reads your data/ folder, and the configuration is valid.
```

---
