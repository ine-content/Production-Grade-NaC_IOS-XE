from nac_validate import RuleBase


class Rule(RuleBase):
    id = "104"
    description = "An OSPF router ID must be the device's Loopback0 address"
    severity = "HIGH"

    @classmethod
    def match(cls, data):
        results = []
        for device in data.get("iosxe", {}).get("devices", []):
            config = device.get("configuration", {})
            loopbacks = config.get("interfaces", {}).get("loopbacks", [])
            address = None
            for loopback in loopbacks:
                if loopback.get("id") == 0:
                    address = loopback.get("ipv4", {}).get("address")
            for process in config.get("routing", {}).get("ospf_processes", []):
                router_id = process.get("router_id")
                if router_id != address:
                    results.append(
                        device["name"] + " OSPF " + str(process.get("id"))
                        + " router_id " + str(router_id)
                        + " is not the Loopback0 address " + str(address)
                    )
        return results
