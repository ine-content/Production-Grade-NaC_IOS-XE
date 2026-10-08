from nac_validate import RuleBase


class Rule(RuleBase):
    id = "102"
    description = "No IPv4 address may be used more than once"
    severity = "HIGH"

    @classmethod
    def match(cls, data):
        users = {}
        for device in data.get("iosxe", {}).get("devices", []):
            pairs = []
            if device.get("host"):
                pairs.append(("host", device["host"]))
            loopbacks = device.get("configuration", {}).get("interfaces", {}).get("loopbacks", [])
            for loopback in loopbacks:
                address = loopback.get("ipv4", {}).get("address")
                if address:
                    pairs.append((f"loopback{loopback.get('id')}", address))
            for where, address in pairs:
                users.setdefault(address, []).append(f"{device['name']}.{where}")
        return [
            f"address {address} is used by {', '.join(owners)}"
            for address, owners in users.items()
            if len(owners) > 1
        ]
