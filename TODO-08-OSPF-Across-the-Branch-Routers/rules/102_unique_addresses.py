from nac_validate import RuleBase


class Rule(RuleBase):
    id = "102"
    description = "Every loopback address must be unique and use a /32 mask"
    severity = "HIGH"

    @classmethod
    def match(cls, data):
        results = []
        seen = {}  # address -> the loopback that used it first
        for device in data.get("iosxe", {}).get("devices", []):
            loopbacks = device.get("configuration", {}).get("interfaces", {}).get("loopbacks", [])
            for loopback in loopbacks:
                label = device["name"] + " Loopback" + str(loopback["id"])
                address = loopback.get("ipv4", {}).get("address")
                mask = loopback.get("ipv4", {}).get("address_mask")
                if address:
                    if mask != "255.255.255.255":
                        results.append(label + " mask is " + str(mask) + ", it must be 255.255.255.255")
                    if address in seen:
                        results.append(address + " is used by " + seen[address] + " and " + label)
                    seen[address] = label
        return results
