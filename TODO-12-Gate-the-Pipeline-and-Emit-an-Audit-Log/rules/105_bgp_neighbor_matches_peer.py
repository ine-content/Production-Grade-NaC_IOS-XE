from nac_validate import RuleBase


class Rule(RuleBase):
    id = "105"
    description = "A BGP neighbor must be another device's Loopback0 and carry that device's AS"
    severity = "HIGH"

    @classmethod
    def match(cls, data):
        devices = data.get("iosxe", {}).get("devices", [])
        owners = {}
        for device in devices:
            config = device.get("configuration", {})
            loopbacks = config.get("interfaces", {}).get("loopbacks", [])
            loopback0 = next((lb for lb in loopbacks if lb.get("id") == 0), {})
            address = loopback0.get("ipv4", {}).get("address")
            asn = config.get("routing", {}).get("bgp", {}).get("as_number")
            if address:
                owners[address] = (device["name"], asn)
        results = []
        for device in devices:
            bgp = device.get("configuration", {}).get("routing", {}).get("bgp", {})
            for neighbor in bgp.get("neighbors", []):
                ip = neighbor.get("ip")
                owner = owners.get(ip)
                if owner is None:
                    results.append(f"{device['name']} neighbor {ip} is not the Loopback0 address of any device")
                elif owner[0] == device["name"]:
                    results.append(f"{device['name']} neighbor {ip} is its own Loopback0 address")
                elif owner[1] != neighbor.get("remote_as"):
                    results.append(
                        f"{device['name']} neighbor {ip} has remote_as {neighbor.get('remote_as')} "
                        f"but {owner[0]} is in AS {owner[1]}"
                    )
        return results
