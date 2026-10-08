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
            loopback0 = next((lb for lb in loopbacks if lb.get("id") == 0), {})
            address = loopback0.get("ipv4", {}).get("address")
            for process in config.get("routing", {}).get("ospf_processes", []):
                router_id = process.get("router_id")
                if router_id != address:
                    results.append(
                        f"{device['name']} OSPF {process.get('id')} router_id {router_id} "
                        f"is not the Loopback0 address {address}"
                    )
        return results
