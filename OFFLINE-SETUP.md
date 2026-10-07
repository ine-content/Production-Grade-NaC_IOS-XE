# Offline Setup

This is everything you need to download while a machine still has internet, and how to install it on a machine that never will.

## What gets downloaded

| Item | Version | Needed from | Size (roughly) |
|------|---------|-------------|----------------|
| Python packages for labs 01-04 (`nac-validate`, `nac-yaml`, PyYAML, rich) | latest | TODO 01 | 3 MB |
| Python packages for labs 05+ (`nac-test`, which pulls in Robot Framework, pyATS and Genie) | latest | TODO 05 | about 200 MB |
| Terraform binary | 1.16.5 | TODO 05 | 25 MB |
| Terraform provider `CiscoDevNet/iosxe` | 1.1.1 | TODO 05 | 30 MB |
| Terraform provider `netascode/utils` | 2.0.3 | TODO 05 | 10 MB |
| Terraform provider `hashicorp/local` | 2.9.1 | TODO 05 | 5 MB |
| Terraform module `netascode/nac-iosxe` | 1.0.0 | TODO 05 | under 1 MB |

You also need Python 3.10 or newer (3.12 is a safe choice) with the `venv` module on the machine that runs the download. Nothing else: no `curl`, no `unzip`, no `sudo`. The scripts fetch and unpack everything with Python itself.

## 1. On a machine with internet

```
cd Production-Grade-NaC_IOS-XE
sh prep/online_download_all.sh
```

Run it on a machine with the same OS family, the same CPU type and the same Python version as the lab machine (for example, both Ubuntu x86_64 with Python 3.12). pyATS and some other packages ship builds for one specific Python version and CPU type, and a bundle made with a different one won't install offline. Check with `python3 --version` and `uname -m` on both. The easiest route is to run the download on the lab machine itself while it is still online.

The script puts everything under `offline-bundle/`. Copy the whole course folder, `offline-bundle/` included, to the offline machine if it isn't already there.

## 2. On the offline lab machine

```
cd Production-Grade-NaC_IOS-XE
sh prep/offline_install.sh
. prep/env.sh
```

This creates a virtual environment in `.venv/`, installs only from `offline-bundle/`, and writes a Terraform config that reads providers from the local mirror, so Terraform never tries to reach the internet.

## 3. Every new terminal

```
cd Production-Grade-NaC_IOS-XE
. prep/env.sh
cd TODO-01-Author-the-Network-Data-Model
python grading.py
```

## Only doing labs 01 to 04?

You can skip all of this. `pip install -r requirements.txt` is enough for those labs (see README).
