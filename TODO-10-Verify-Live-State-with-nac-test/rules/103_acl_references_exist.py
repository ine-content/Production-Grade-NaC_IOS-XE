from nac_validate import RuleBase


class Rule(RuleBase):
    id = "103"
    description = "An interface may only use an ACL that the same device defines"
    severity = "HIGH"

    @classmethod
    def match(cls, data):
        results = []
        for device in data.get("iosxe", {}).get("devices", []):
            config = device.get("configuration", {})
            lists = config.get("access_lists", {})
            defined = set()
            for acl in lists.get("standard", []):
                defined.add(acl["name"])
            for loopback in config.get("interfaces", {}).get("loopbacks", []):
                name = loopback.get("ipv4", {}).get("access_group_in")
                if name and name not in defined:
                    results.append(
                        device["name"] + " Loopback" + str(loopback.get("id")) + " uses ACL '"
                        + name + "', which the device does not define"
                    )
        return results
