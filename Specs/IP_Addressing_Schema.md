# TECHVIET INNOVATIONS (TVI) - IP ADDRESSING & PORT MAPPING CONTRACT

Tài liệu này là **Hợp đồng Kỹ thuật dùng chung (Immutable Technical Contract)** cho cả 4 thành viên. Khi viết câu lệnh cấu hình vào file `.cfg` hoặc code Python tự động hóa, mọi người **bắt buộc** sử dụng đúng Tên thiết bị (Hostname), số hiệu VLAN, tên cổng (Interface) và địa chỉ IPv4/IPv6 trong tài liệu này để khi ghép bài không xảy ra xung đột.

---

## 1. Danh mục VLAN Chuẩn Toàn Hệ Thống (System-Wide VLANs)

| VLAN ID | Tên Chuẩn (VLAN Name) | Khu vực áp dụng | Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| **`10`** | `EXEC_FINANCE` | TP.HCM (HQ) | Ban Giám đốc, Tài chính & Máy chủ nội bộ (DHCP/DNS/NTP: `10.10.10.50`) |
| **`20`** | `RND_ENGINEERING` | TP.HCM (HQ) & Hà Nội | Kỹ sư phần mềm tại HQ & Phòng Lab AI tại Hà Nội |
| **`30`** | `LOGISTICS_OPS` | Đà Nẵng | Hệ thống quản lý kho vận & Thiết bị cảm biến IoT |
| **`50`** | `GUEST_WIFI` | Hà Nội | Mạng Wi-Fi Khách (Cách ly hoàn toàn khỏi mạng nội bộ bằng ACL) |
| **`99`** | `MANAGEMENT` | Toàn hệ thống (3 miền) | Mạng quản trị thiết bị qua SSHv2 & chạy script Python Netmiko |
| **`999`** | `BLACKHOLE` | Toàn hệ thống (3 miền) | Cô lập toàn bộ các cổng Switch không sử dụng (`shutdown`) |

---

## 2. Bảng Quy Hoạch Địa Chỉ IPv4 (VLSM) & IPv6 (Dual-Stack)

Công thức tính số Host khả dụng: $\text{Usable Hosts} = 2^{(32 - \text{Prefix})} - 2$.

| Khu vực (Site) | Phân vùng / Mục đích | Nhu cầu | Dải mạng IPv4 (CIDR) | Subnet Mask | Dải IP Khả dụng (Usable Range) | Broadcast IP | Default Gateway | Dải mạng IPv6 (`/64`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TP.HCM (HQ)** | `VLAN 20` (`RND_ENGINEERING`) | ~400 hosts | `10.10.20.0/23` | `255.255.254.0` | `10.10.20.1` – `10.10.21.254` | `10.10.21.255` | `10.10.20.1` (HSRP) | `2001:DB8:10:20::/64` |
| **TP.HCM (HQ)** | `VLAN 10` (`EXEC_FINANCE`) | ~150 hosts | `10.10.10.0/24` | `255.255.255.0` | `10.10.10.1` – `10.10.10.254` | `10.10.10.255` | `10.10.10.1` (HSRP) | `2001:DB8:10:10::/64` |
| **TP.HCM (HQ)** | `VLAN 99` (`MANAGEMENT`) | ~50 nodes | `192.168.1.0/24` | `255.255.255.0` | `192.168.1.1` – `192.168.1.254` | `192.168.1.255` | `192.168.1.1` (HSRP) | `2001:DB8:10:99::/64` |
| **Hà Nội (R&D)** | `VLAN 20` (`RND_ENGINEERING`) | ~350 hosts | `10.20.20.0/23` | `255.255.254.0` | `10.20.20.1` – `10.20.21.254` | `10.20.21.255` | `10.20.20.1` | `2001:DB8:20:20::/64` |
| **Hà Nội (R&D)** | `VLAN 50` (`GUEST_WIFI`) | ~100 khách | `10.20.50.0/25` | `255.255.255.128` | `10.20.50.1` – `10.20.50.126` | `10.20.50.127` | `10.20.50.1` | `2001:DB8:20:50::/64` |
| **Hà Nội (R&D)** | `VLAN 99` (`MANAGEMENT`) | ~30 nodes | `192.168.2.0/24` | `255.255.255.0` | `192.168.2.1` – `192.168.2.254` | `192.168.2.255` | `192.168.2.1` | `2001:DB8:20:99::/64` |
| **Đà Nẵng (Hub)** | `VLAN 30` (`LOGISTICS_OPS`) | ~200 IoT/PC | `10.30.30.0/24` | `255.255.255.0` | `10.30.30.1` – `10.30.30.254` | `10.30.30.255` | `10.30.30.1` | `2001:DB8:30:30::/64` |
| **Đà Nẵng (Hub)** | `VLAN 99` (`MANAGEMENT`) | ~20 nodes | `192.168.3.0/24` | `255.255.255.0` | `192.168.3.1` – `192.168.3.254` | `192.168.3.255` | `192.168.3.1` | `2001:DB8:30:99::/64` |
| **Nội bộ HQ L3** | Link `EDGE-RTR01` <-> `DIST-SW01` | 2 đầu dây | `10.10.254.0/30` | `255.255.255.252` | `.1` (RTR) và `.2` (DIST01) | `10.10.254.3` | Point-to-Point OSPF | `2001:DB8:10:2541::/64` |
| **Nội bộ HQ L3** | Link `EDGE-RTR01` <-> `DIST-SW02` | 2 đầu dây | `10.10.254.4/30` | `255.255.255.252` | `.5` (RTR) và `.6` (DIST02) | `10.10.254.7` | Point-to-Point OSPF | `2001:DB8:10:2542::/64` |
| **WAN (eBGP)** | Link `HCMC-EDGE` <-> `ISP-CORE` | 2 đầu dây | `203.0.113.0/30` | `255.255.255.252` | `.1` (HQ) và `.2` (ISP) | `203.0.113.3` | eBGP AS 65001–65000 | `2001:DB8:FFFF:1::/64` |
| **WAN (eBGP)** | Link `HANOI-RTR` <-> `ISP-CORE` | 2 đầu dây | `203.0.113.4/30` | `255.255.255.252` | `.5` (HN) và `.6` (ISP) | `203.0.113.7` | eBGP AS 65002–65000 | `2001:DB8:FFFF:2::/64` |
| **WAN (eBGP)** | Link `DANANG-RTR` <-> `ISP-CORE` | 2 đầu dây | `203.0.113.8/30` | `255.255.255.252` | `.9` (DN) và `.10` (ISP) | `203.0.113.11` | eBGP AS 65003–65000 | `2001:DB8:FFFF:3::/64` |
| **VPN Overlay** | `Tunnel12` (HQ <-> Hà Nội) | 2 đầu hầm | `172.16.12.0/30` | `255.255.255.252` | `.1` (HQ) và `.2` (HN) | `172.16.12.3` | GRE over IPsec | `2001:DB8:CAFE:12::/64` |
| **VPN Overlay** | `Tunnel13` (HQ <-> Đà Nẵng) | 2 đầu hầm | `172.16.13.0/30` | `255.255.255.252` | `.1` (HQ) và `.2` (DN) | `172.16.13.3` | GRE over IPsec | `2001:DB8:CAFE:13::/64` |

### 2.1. Quy hoạch Phân cấp Tổng thể, Dự phòng Mở rộng 10,000+ Thiết bị & Gộp tuyến (Route Summarization)

Để đáp ứng yêu cầu mở rộng của tập đoàn TVI lên **4,000+ nhân sự chính thức, 10,000+ thiết bị IoT vào năm 2030** và tối ưu kích thước bảng định tuyến toàn cầu (BGP/OSPF Route Summarization), không gian địa chỉ của mỗi vùng được cấp phát theo cấu trúc **Supernet `/16` (IPv4)** và **`/48` (IPv6)**:

| Khu vực (Region) | BGP AS | Khối Supernet IPv4 (Gộp tuyến BGP/OSPF) | Tổng dung lượng IPv4 | Các Subnet đang triển khai (Lab) | Không gian dự phòng mở rộng (2026–2030) | Khối IPv6 Site Prefix (`/48`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TP.HCM (HQ)** | `AS 65001` | `10.10.0.0/16` & `192.168.1.0/24` | `65,534` hosts | `10.10.10.0/24` (Exec)<br>`10.10.20.0/23` (R&D)<br>`10.10.254.0/29` (L3 Links) | `10.10.32.0/19` (`8,190` hosts cho Campus mở rộng)<br>`10.10.64.0/18` (`16,382` hosts cho Data Center Fabric) | `2001:DB8:10::/48` |
| **Hà Nội (R&D)** | `AS 65002` | `10.20.0.0/16` & `192.168.2.0/24` | `65,534` hosts | `10.20.20.0/23` (R&D AI)<br>`10.20.50.0/25` (Guest Wi-Fi) | `10.20.32.0/20` (`4,094` hosts cho cụm GPU/AI Cluster)<br>`10.20.64.0/19` (`8,190` hosts cho kỹ sư R&D mới) | `2001:DB8:20::/48` |
| **Đà Nẵng (Hub)** | `AS 65003` | `10.30.0.0/16` & `192.168.3.0/24` | `65,534` hosts | `10.30.30.0/24` (Logistics Ops) | `10.30.64.0/18` (`16,382` endpoints cho cảm biến IoT & AGV kho vận) | `2001:DB8:30::/48` |

---

## 3. Bảng Đấu Dây Chi Tiết Từng Cổng (Port-by-Port Interface Mapping)

| STT | Tên Thiết Bị (Hostname) | Cổng (Interface) | Đấu nối sang Thiết bị & Cổng nào? | Chế độ (Mode) / Giao thức | Địa chỉ IPv4 & IPv6 Dual-Stack |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **`ISP-CORE-RTR01`**<br>*(BGP AS 65000)* | `Gi0/0`<br>`Gi0/1`<br>`Gi0/2`<br>`Loopback0` | -> `HCMC-EDGE-RTR01` (`Gi0/0`)<br>-> `HANOI-RND-RTR01` (`Gi0/0`)<br>-> `DANANG-LOG-RTR01` (`Gi0/0`)<br>*Cổng ảo giả lập Internet DNS* | Layer 3 (eBGP)<br>Layer 3 (eBGP)<br>Layer 3 (eBGP)<br>Loopback | `203.0.113.2/30` \| `2001:DB8:FFFF:1::2/64`<br>`203.0.113.6/30` \| `2001:DB8:FFFF:2::2/64`<br>`203.0.113.10/30` \| `2001:DB8:FFFF:3::2/64`<br>`8.8.8.8/32` \| `2001:4860:4860::8888/128` |
| **2** | **`HCMC-EDGE-RTR01`**<br>*(BGP AS 65001)* | `Gi0/0`<br>`Gi0/1`<br>`Gi0/2`<br>`Loopback0`<br>`Tunnel12`<br>`Tunnel13` | -> `ISP-CORE-RTR01` (`Gi0/0`)<br>-> `HCMC-DIST-SW01` (`Gi0/1`)<br>-> `HCMC-DIST-SW02` (`Gi0/1`)<br>*OSPF Router-ID*<br>-> `HANOI-RND-RTR01` (`Tunnel12`)<br>-> `DANANG-LOG-RTR01` (`Tunnel13`) | `ip nat outside` + eBGP + QoS<br>`ip nat inside` + OSPF Area 0<br>`ip nat inside` + OSPF Area 0<br>OSPF Area 0<br>IPsec VPN + OSPF Area 0 + QoS<br>IPsec VPN + OSPF Area 0 + QoS | `203.0.113.1/30` \| `2001:DB8:FFFF:1::1/64`<br>`10.10.254.1/30` \| `2001:DB8:10:2541::1/64`<br>`10.10.254.5/30` \| `2001:DB8:10:2542::1/64`<br>`10.255.255.1/32` \| `2001:DB8:10:FFFF::1/128`<br>`172.16.12.1/30` \| `2001:DB8:CAFE:12::1/64`<br>`172.16.13.1/30` \| `2001:DB8:CAFE:13::1/64` |
| **3** | **`HCMC-DIST-SW01`**<br>*(L3 Switch - HSRP Active & STP Root Primary)* | `Gi0/1`<br>`Gi0/2` & `Gi0/3`<br>`Gi0/4`<br>`Vlan 10`<br>`Vlan 20`<br>`Vlan 99`<br>`Loopback0` | -> `HCMC-EDGE-RTR01` (`Gi0/1`)<br>-> `HCMC-DIST-SW02` (`Gi0/2`, `Gi0/3`)<br>-> `HCMC-CORE-SW01` (`Gi0/1`)<br>*SVI Gateway (HSRP VIP: `10.10.10.1`)*<br>*SVI Gateway (HSRP VIP: `10.10.20.1`)*<br>*SVI Gateway (HSRP VIP: `192.168.1.1`)*<br>*OSPF Router-ID* | Layer 3 (`no switchport`)<br>LACP Trunk (`Port-channel 1`)<br>802.1Q Trunk<br>HSRP Grp 10 (`Prio 110`, `Preempt`)<br>HSRP Grp 20 (`Prio 110`) + DHCP Relay<br>HSRP Grp 99 (`Prio 110`, `Preempt`)<br>OSPF Area 0 | `10.10.254.2/30` \| `2001:DB8:10:2541::2/64`<br>*(Layer 2 Trunk)*<br>*(Layer 2 Trunk)*<br>`10.10.10.2/24` \| `2001:DB8:10:10::2/64`<br>`10.10.20.2/23` \| `2001:DB8:10:20::2/64`<br>`192.168.1.2/24` \| `2001:DB8:10:99::2/64`<br>`10.255.255.11/32` \| `2001:DB8:10:FFFF::11/128` |
| **4** | **`HCMC-DIST-SW02`**<br>*(L3 Switch - HSRP Standby & STP Root Secondary)* | `Gi0/1`<br>`Gi0/2` & `Gi0/3`<br>`Gi0/4`<br>`Vlan 10`<br>`Vlan 20`<br>`Vlan 99`<br>`Loopback0` | -> `HCMC-EDGE-RTR01` (`Gi0/2`)<br>-> `HCMC-DIST-SW01` (`Gi0/2`, `Gi0/3`)<br>-> `HCMC-CORE-SW01` (`Gi0/2`)<br>*SVI Gateway (HSRP VIP: `10.10.10.1`)*<br>*SVI Gateway (HSRP VIP: `10.10.20.1`)*<br>*SVI Gateway (HSRP VIP: `192.168.1.1`)*<br>*OSPF Router-ID* | Layer 3 (`no switchport`)<br>LACP Trunk (`Port-channel 1`)<br>802.1Q Trunk<br>HSRP Grp 10 (`Prio 100`)<br>HSRP Grp 20 (`Prio 100`) + DHCP Relay<br>HSRP Grp 99 (`Prio 100`)<br>OSPF Area 0 | `10.10.254.6/30` \| `2001:DB8:10:2542::2/64`<br>*(Layer 2 Trunk)*<br>*(Layer 2 Trunk)*<br>`10.10.10.3/24` \| `2001:DB8:10:10::3/64`<br>`10.10.20.3/23` \| `2001:DB8:10:20::3/64`<br>`192.168.1.3/24` \| `2001:DB8:10:99::3/64`<br>`10.255.255.12/32` \| `2001:DB8:10:FFFF::12/128` |
| **5** | **`HCMC-CORE-SW01`**<br>*(L2 Access Switch)* | `Gi0/1`<br>`Gi0/2`<br>`Fa0/1` – `Fa0/10`<br>`Fa0/11` – `Fa0/20`<br>`Fa0/24`<br>`Vlan 99` | -> `HCMC-DIST-SW01` (`Gi0/4`)<br>-> `HCMC-DIST-SW02` (`Gi0/4`)<br>-> PC Ban Giám đốc & Server (`.50`)<br>-> PC Kỹ sư HQ<br>-> Máy trạm Quản trị (Automation Node)<br>*IP Quản trị SSH cho Step 9* | 802.1Q Trunk (DHCP Snooping Trust)<br>802.1Q Trunk (DHCP Snooping Trust)<br>Access `VLAN 10` + PortFast + PortSec<br>Access `VLAN 20` + PortFast + PortSec<br>Access `VLAN 99` + PortFast<br>Management SVI (`GW: 192.168.1.1`) | *(Layer 2 Trunk)*<br>*(Layer 2 Trunk)*<br>*(Layer 2 Access)*<br>*(Layer 2 Access)*<br>*(Layer 2 Access)*<br>`192.168.1.10/24` \| `2001:DB8:10:99::10/64` |
| **6** | **`HANOI-RND-RTR01`**<br>*(BGP AS 65002)* | `Gi0/0`<br>`Gi0/1.20`<br>`Gi0/1.50`<br>`Gi0/1.99`<br>`Loopback0`<br>`Tunnel12` | -> `ISP-CORE-RTR01` (`Gi0/1`)<br>-> `HANOI-RND-SW01` (`Gi0/1`)<br>-> `HANOI-RND-SW01` (`Gi0/1`)<br>-> `HANOI-RND-SW01` (`Gi0/1`)<br>*OSPF Router-ID*<br>-> `HCMC-EDGE-RTR01` (`Tunnel12`) | `ip nat outside` + eBGP + QoS<br>Sub-if `dot1Q 20` + DHCP Relay<br>Sub-if `dot1Q 50` + DHCP Relay + ACL<br>Sub-if `dot1Q 99`<br>OSPF Area 0<br>IPsec VPN + OSPF Area 0 + QoS | `203.0.113.5/30` \| `2001:DB8:FFFF:2::1/64`<br>`10.20.20.1/23` \| `2001:DB8:20:20::1/64`<br>`10.20.50.1/25` \| `2001:DB8:20:50::1/64`<br>`192.168.2.1/24` \| `2001:DB8:20:99::1/64`<br>`10.255.255.2/32` \| `2001:DB8:20:FFFF::2/128`<br>`172.16.12.2/30` \| `2001:DB8:CAFE:12::2/64` |
| **7** | **`HANOI-RND-SW01`** & **`SW02`**<br>*(L2 Switches)* | `Gi0/1` (trên SW01)<br>`Gi0/2` & `Gi0/3`<br>`Fa0/1` – `Fa0/15`<br>`Fa0/16` – `Fa0/20`<br>`Vlan 99` | -> `HANOI-RND-RTR01` (`Gi0/1`)<br>Nối chéo `SW01` <-> `SW02`<br>-> PC Phòng Lab AI Hà Nội<br>-> Access Point Wi-Fi Khách<br>*IP Quản trị SSH cho Step 9* | 802.1Q Trunk (DHCP Snooping Trust)<br>LACP Trunk (`Port-channel 1`)<br>Access `VLAN 20` + PortFast + PortSec<br>Access `VLAN 50` + PortFast<br>Management SVI (`GW: 192.168.2.1`) | *(Layer 2 Trunk)*<br>*(Layer 2 Trunk)*<br>*(Layer 2 Access)*<br>*(Layer 2 Access)*<br>SW01: `192.168.2.10/24` \| `2001:DB8:20:99::10/64`<br>SW02: `192.168.2.11/24` \| `2001:DB8:20:99::11/64` |
| **8** | **`DANANG-LOG-RTR01`**<br>*(BGP AS 65003)* | `Gi0/0`<br>`Gi0/1.30`<br>`Gi0/1.99`<br>`Loopback0`<br>`Tunnel13` | -> `ISP-CORE-RTR01` (`Gi0/2`)<br>-> `DANANG-LOG-SW01` (`Gi0/1`)<br>-> `DANANG-LOG-SW01` (`Gi0/1`)<br>*OSPF Router-ID*<br>-> `HCMC-EDGE-RTR01` (`Tunnel13`) | `ip nat outside` + eBGP + QoS<br>Sub-if `dot1Q 30` + DHCP Relay<br>Sub-if `dot1Q 99`<br>OSPF Area 0<br>IPsec VPN + OSPF Area 0 + QoS | `203.0.113.9/30` \| `2001:DB8:FFFF:3::1/64`<br>`10.30.30.1/24` \| `2001:DB8:30:30::1/64`<br>`192.168.3.1/24` \| `2001:DB8:30:99::1/64`<br>`10.255.255.3/32` \| `2001:DB8:30:FFFF::3/128`<br>`172.16.13.2/30` \| `2001:DB8:CAFE:13::2/64` |
| **9** | **`DANANG-LOG-SW01`**<br>*(L2 Switch)* | `Gi0/1`<br>`Fa0/1` – `Fa0/20`<br>`Vlan 99` | -> `DANANG-LOG-RTR01` (`Gi0/1`)<br>-> Thiết bị kho vận & cảm biến IoT<br>*IP Quản trị SSH cho Step 9* | 802.1Q Trunk (DHCP Snooping Trust)<br>Access `VLAN 30` + PortFast + PortSec<br>Management SVI (`GW: 192.168.3.1`) | *(Layer 2 Trunk)*<br>*(Layer 2 Access)*<br>`192.168.3.10/24` \| `2001:DB8:30:99::10/64` |

---

## 4. Thông Số Dịch Vụ Tập Trung & Quản Trị Tự Động Hóa (Step 4 & Step 9)

- **DHCP, DNS & NTP Server tập trung (Đặt tại VLAN 10 HQ):** `10.10.10.50`
  - **Tại TP.HCM (HQ):** `HCMC-DIST-SW01` và `HCMC-DIST-SW02` cấu hình `ip helper-address 10.10.10.50` trên `interface Vlan 20` (và `interface Vlan 99` nếu cấp động).
  - **Tại Hà Nội (R&D):** `HANOI-RND-RTR01` cấu hình `ip helper-address 10.10.10.50` trên `interface Gi0/1.20` và `interface Gi0/1.50`.
  - **Tại Đà Nẵng (Logistics):** `DANANG-LOG-RTR01` cấu hình `ip helper-address 10.10.10.50` trên `interface Gi0/1.30`.
- **Cấu hình Default Gateway bắt buộc trên các Switch Layer 2 (Để SSH xuyên vùng từ HQ):**
  - `HCMC-CORE-SW01`: `ip default-gateway 192.168.1.1`
  - `HANOI-RND-SW01` & `HANOI-RND-SW02`: `ip default-gateway 192.168.2.1`
  - `DANANG-LOG-SW01`: `ip default-gateway 192.168.3.1`
- **Danh sách IP Quản trị SSHv2 cho `Automation/inventory.yaml` (Step 9):**
  - `HCMC-CORE-SW01`: `192.168.1.10`
  - `HANOI-RND-SW01`: `192.168.2.10`
  - `DANANG-LOG-SW01`: `192.168.3.10`
  - *(Mở rộng tùy chọn)* `HANOI-RND-SW02`: `192.168.2.11`
