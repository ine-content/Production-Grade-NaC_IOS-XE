from nac_validate import RuleBase


class Rule(RuleBase):
    id = "101"
    description = "Device hostname must equal its device name"
    severity = "HIGH"

    @classmethod
    def match(cls, data):
        results = []
        for device in data.get("iosxe", {}).get("devices", []):
            hostname = device.get("configuration", {}).get("system", {}).get("hostname")
            if hostname != device["name"]:
                results.append(
                    f"iosxe.devices[name={device['name']}].configuration.system.hostname - "
                    f"'{hostname}' does not match the device name"
                )
        return results
