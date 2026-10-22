*** Settings ***
Documentation     The live routers match the data model
Library           RequestsLibrary

*** Keywords ***
Router Get
    [Documentation]    GET one RESTCONF path from a router and return the data under its top-level key.
    [Arguments]    ${host}    ${path}
    ${auth}=    Create List    %{IOSXE_USERNAME}    %{IOSXE_PASSWORD}
    Create Session    ${host}    https://${host}    auth=${auth}    verify=${FALSE}
    ${headers}=    Create Dictionary    Accept=application/yang-data+json
    ${response}=    GET On Session    ${host}    /restconf/data/${path}    headers=${headers}    expected_status=200
    ${data}=    Evaluate    next(iter($response.json().values()))
    RETURN    ${data}

Neighbor Should Be Full
    [Documentation]    Fail unless the OSPF data shows this neighbor router ID in state FULL.
    [Arguments]    ${state}    ${neighbor_id}
    ${objects}=    Evaluate    (lambda walk, data: walk(walk, data))(lambda walk, x: ([x] if isinstance(x, dict) else []) + [y for v in (list(x.values()) if isinstance(x, dict) else x if isinstance(x, list) else []) for y in walk(walk, v)], $state)
    ${states}=    Evaluate    [str(o.get('state')) for o in $objects if o.get('neighbor-id') == '${neighbor_id}']
    Should Not Be Empty    ${states}    No OSPF neighbor ${neighbor_id} in the neighbor table
    ${full}=    Evaluate    any('full' in s.lower() for s in $states)
    Should Be True    ${full}    Neighbor ${neighbor_id} is not FULL. States seen: ${states}

*** Test Cases ***
{% for device in iosxe.devices | default([]) %}
{{ device.name }} hostname
    [Tags]    iosxe    system
    ${hostname}=    Router Get    {{ device.host }}    Cisco-IOS-XE-native:native/hostname
    Should Be Equal    ${hostname}    {{ device.configuration.system.hostname }}

{% for loopback in device.configuration.interfaces.loopbacks | default([]) %}
{{ device.name }} Loopback{{ loopback.id }}
    [Tags]    iosxe    interfaces
    ${entries}=    Router Get    {{ device.host }}    Cisco-IOS-XE-native:native/interface/Loopback={{ loopback.id }}
    ${text}=    Convert To String    ${entries}[0]
    Should Contain    ${text}    {{ loopback.ipv4.address }}

{% endfor %}
{% set my_processes = (device.configuration.routing | default({})).ospf_processes | default([]) %}
{% if my_processes | length > 0 %}
{% for other in iosxe.devices | default([]) %}
{% set other_processes = (other.configuration.routing | default({})).ospf_processes | default([]) %}
{% if other.name != device.name and other_processes | length > 0 %}
{{ device.name }} OSPF neighbor {{ other_processes[0].router_id }}
    [Tags]    iosxe    ospf    operational
    ${state}=    Router Get    {{ device.host }}    Cisco-IOS-XE-ospf-oper:ospf-oper-data/ospf-state
    Neighbor Should Be Full    ${state}    {{ other_processes[0].router_id }}

{% endif %}
{% endfor %}
{% endif %}
{% endfor %}
