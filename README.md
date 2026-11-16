# TechViet Innovations (TVI) - Enterprise Network Design & Implementation

**Course:** Computer Networking & Network Administration (`CO3093` / `CO3094`) — Ho Chi Minh City University of Technology (HCMUT)  
**Group:** Group 10 (`TVI_Project_Group10`)  
**Repository:** https://github.com/ReijiNgo/TVI_Project_Group10

---

## 1. Project Overview

This project designs and implements a scalable, redundant, secure, and automated next-generation enterprise network for **TechViet Innovations (TVI)** across three regional campuses in Vietnam connected via an ISP core:

- **Headquarters (TP.HCM - HQ, BGP `AS 65001`):** Dual-Distribution L3 switching with HSRP gateway redundancy, LACP EtherChannel, Rapid-PVST+, centralized DHCP/DNS/NTP (`10.10.10.50`), and Edge routing (`HCMC-EDGE-RTR01`, `HCMC-DIST-SW01`, `HCMC-DIST-SW02`, `HCMC-CORE-SW01`).
- **R&D & Engineering Campus (Hà Nội, BGP `AS 65002`):** High-bandwidth compute LAN (`VLAN 20`) and strictly isolated Guest Wi-Fi (`VLAN 50`) (`HANOI-RND-RTR01`, `HANOI-RND-SW01`, `HANOI-RND-SW02`).
- **Logistics & Distribution Hub (Đà Nẵng, BGP `AS 65003`):** Warehouse & IoT automation LAN (`VLAN 30`) (`DANANG-LOG-RTR01`, `DANANG-LOG-SW01`).
- **Simulated ISP Core (BGP `AS 65000`):** Inter-site WAN peering and simulated public DNS (`8.8.8.8/32`) (`ISP-CORE-RTR01`).

All 10 network devices strictly follow the immutable IPv4 VLSM, IPv6 Dual-Stack, VLAN, and port-mapping contract defined in [`Specs/IP_Addressing_Schema.md`](Specs/IP_Addressing_Schema.md).

---

## 2. Repository Structure

```text
TVI_Project_Group10/
├── README.md                          # Project documentation & automation runbook
├── Specs/
│   └── IP_Addressing_Schema.md        # Immutable IPv4/IPv6, VLAN & Port-by-Port Contract (Step 1 & 2)
├── Configurations/                    # Final merged startup-configs for all 10 devices (Step 10)
│   ├── HQ_Startup_Configs/
│   ├── Hanoi_Startup_Configs/
│   └── DaNang_Startup_Configs/
├── Draft_Modules/                     # Isolated working directories for parallel team development
│   ├── member1_switching_dhcp/        # Step 3 & 4: VLAN, 802.1Q, LACP, Rapid-PVST+, HSRP, DHCP Relay
│   ├── member2_routing_wan_qos/       # Step 5, 6 & 8: OSPFv2/v3, eBGP, GRE over IPsec VPN, LLQ QoS
│   └── member3_security_nat/          # Step 7: PAT/NAT Overload, ACLs, L2 Security, SSHv2 Hardening
├── Automation/                        # Step 9: Python Netmiko + PyYAML IaC workflow
│   ├── inventory.yaml                 # Externalized device inventory (VLAN 99 Management IPs)
│   ├── auto_provision.py              # Automated config backup, VLAN/NTP/Banner push & logging
│   ├── backups/                       # Timestamped running-config backups
│   └── logs/                          # Execution and SSH error logs (automation.log)
└── Report/                            # Step 10: Draw.io diagrams, LaTeX source & Technical PDF Report
```

---

## 3. Team Roles & Zero-Conflict Git Workflow

| Member | Role / Scope | Assigned Branch | Working Directory |
| :--- | :--- | :--- | :--- |
| **Member 1** | Switching, STP, LACP, HSRP & DHCP (Step 3–4) | `feature/switching-dhcp` | `Draft_Modules/member1_switching_dhcp/` |
| **Member 2** | OSPFv2/v3, eBGP, IPsec VPN & QoS (Step 5–6, 8) | `feature/routing-wan-qos` | `Draft_Modules/member2_routing_wan_qos/` |
| **Member 3** | NAT/PAT, ACLs, L2 Security & Python Automation (Step 7, 9) | `feature/security-automation` | `Draft_Modules/member3_security_nat/`, `Automation/` |
| **Member 4 (Leader)** | Topology Design, IP Schema, Integration, QA & LaTeX Report (Step 1–2, 10) | `feature/design-qa-report` | `Specs/`, `Configurations/`, `Report/` |

### Quick Git Commands for Team Members
```bash
git clone https://github.com/ReijiNgo/TVI_Project_Group10.git
cd TVI_Project_Group10
git checkout <your-assigned-branch>
```

---

## 4. Network Automation Setup & Usage (Step 9)

### Prerequisites
- Python 3.8+ installed on the Management / Automation Control Node connected to `VLAN 99` (`192.168.1.0/24`, reachable across HQ, Hanoi, and Da Nang via OSPF/IPsec).
- SSHv2 enabled on target switches (`HCMC-CORE-SW01`: `192.168.1.10`, `HANOI-RND-SW01`: `192.168.2.10`, `DANANG-LOG-SW01`: `192.168.3.10`).

### Step-by-Step Execution
1. **Install Python dependencies:**
   ```bash
   pip install netmiko pyyaml paramiko
   ```
2. **Navigate to the `Automation` directory:**
   ```bash
   cd Automation
   ```
3. **Verify target inventory:**
   Ensure `inventory.yaml` lists all target nodes with accurate management IPs and `device_type: cisco_ios`.
4. **Run the automation script:**
   ```bash
   python auto_provision.py
   ```
   - Enter the SSH username and password interactively when prompted (`getpass` — no credentials are hardcoded).
   - The script captures pre/post device state (`show running-config` and `show ip interface brief`), saves timestamped backups to `Automation/backups/`, deploys NTP (`10.10.10.50`), MOTD banner, and standard VLANs (`10, 20, 30, 99`), and writes execution/error logs to `Automation/logs/automation.log`.
