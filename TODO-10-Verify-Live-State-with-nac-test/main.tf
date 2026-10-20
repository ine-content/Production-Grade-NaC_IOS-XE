terraform {
  required_version = ">= 1.9.0"
}

module "iosxe" {
  source           = "../offline-bundle/modules/nac-iosxe"
  yaml_directories = ["data"]
  managed_devices  = ["R10", "R11", "R12"]
}
