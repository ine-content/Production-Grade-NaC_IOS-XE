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
{% for neighbor in device.configuration.routing.bgp.neighbors | default([]) %}
{{ device.name }} BGP neighbor {{ neighbor.ip }}
    [Tags]    iosxe    bgp
    ${neighbors}=    Router Get    {{ device.host }}    Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors
    ${found}=    Evaluate    [n for n in $neighbors['neighbor'] if n['neighbor-id'] == '{{ neighbor.ip }}']
    Should Not Be Empty    ${found}    no BGP session to {{ neighbor.ip }} on {{ device.name }}
    Should Be Equal    ${found}[0][session-state]    fsm-established
    Should Be Equal As Integers    ${found}[0][as]    {{ neighbor.remote_as }}

{% endfor %}
{% endfor %}
