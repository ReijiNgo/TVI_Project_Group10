# THÀNH VIÊN 2: HƯỚNG DẪN LÀM BÀI MẢNG ROUTING (OSPF/BGP), IPSEC VPN & QOS (STEP 5, STEP 6 & STEP 8)

- **Nhánh Git làm việc:** `feature/routing-wan-qos`
- **File soạn thảo chính:** `Draft_Modules/member2_routing_wan_qos/member2_routing_wan_qos_draft.cfg`
- **Tài liệu tham chiếu bắt buộc:** [`Specs/IP_Addressing_Schema.md`](../../Specs/IP_Addressing_Schema.md)

> **Lưu ý Zero-Conflict:** Tuyệt đối giữ nguyên toàn bộ BGP AS, Router-ID Loopback0, dải IPv4/IPv6 WAN (`203.0.113.x/30` và `2001:DB8:FFFF:x::/64`) và Tunnel IP (`172.16.12.0/30`, `172.16.13.0/30` và `2001:DB8:CAFE:x::/64`) đã chốt trong `Specs/IP_Addressing_Schema.md`.

---

## Danh sách công việc cần hoàn thành (Checklist theo Rubric & Pre-Submission Checklist)

### 1. Step 5: Underlay Routing (IGP - OSPFv2 & OSPFv3)
- [ ] **Kích hoạt Dual-Stack Routing:** Bật `ip routing` và `ipv6 unicast-routing` trên `HCMC-EDGE-RTR01`, `HCMC-DIST-SW01`, `HCMC-DIST-SW02`, `HANOI-RND-RTR01`, `DANANG-LOG-RTR01`.
- [ ] **OSPFv2 (IPv4) & OSPFv3 (IPv6) Area 0:**
  - `HCMC-EDGE-RTR01`: `router-id 10.255.255.1` (quảng bá Link L3 `10.10.254.0/30`, `10.10.254.4/30`, Loopback0, Tunnel12, Tunnel13).
  - `HCMC-DIST-SW01`: `router-id 10.255.255.11` (quảng bá `10.10.254.0/30`, VLAN 10/20/99, Loopback0).
  - `HCMC-DIST-SW02`: `router-id 10.255.255.12` (quảng bá `10.10.254.4/30`, VLAN 10/20/99, Loopback0).
  - `HANOI-RND-RTR01`: `router-id 10.255.255.2` (quảng bá VLAN 20/50/99, Loopback0, Tunnel12).
  - `DANANG-LOG-RTR01`: `router-id 10.255.255.3` (quảng bá VLAN 30/99, Loopback0, Tunnel13).
- [ ] **Passive Interface:** Bật `passive-interface` trên các cổng VLAN người dùng (SVI/Sub-interface) để không phát gói Hello OSPF xuống máy trạm.
- [ ] **Tắt keepalive trên link P2P ảo:** Thêm `no keepalive` trên các cổng `Gi0/1`, `Gi0/2` nối giữa Router HQ và Distribution Switch (theo hướng dẫn trang 21 đề bài).

### 2. Step 6: Overlay Routing (eBGP) & IPsec VPN Tunnels
- [ ] **Nhà mạng giả lập `ISP-CORE-RTR01` (BGP AS `65000`):**
  - Loopback0 DNS giả lập: `8.8.8.8/32` (`2001:4860:4860::8888/128`).
  - Thiết lập phiên eBGP với 3 Router biên: HQ (`AS 65001` - `203.0.113.1`), Hà Nội (`AS 65002` - `203.0.113.5`), Đà Nẵng (`AS 65003` - `203.0.113.9`).
  - Quảng bá `8.8.8.8/32` (hoặc default-originate) cho các chi nhánh đi Internet.
- [ ] **eBGP trên 3 Router biên & Route Summarization:**
  - Thiết lập eBGP peering với `ISP-CORE-RTR01` (`AS 65000`).
  - Cấu hình **Route Summarization** (hoặc `aggregate-address`) các dải tổng (`10.10.0.0/16`, `10.20.0.0/16`, `10.30.0.0/16`) tại biên để tối ưu bảng định tuyến toàn cầu (trừ phần WAN public không quảng bá nhầm dải private nếu chạy NAT - ghi chú rõ cơ chế phối hợp với NAT của Thành viên 3).
- [ ] **GRE over IPsec VPN (`Tunnel12` & `Tunnel13`):**
  - Thiết lập ISAKMP Policy (IKEv1/IKEv2, AES-256, SHA-256, Group 14), Pre-shared Key, IPsec Transform-Set (`esp-aes 256 esp-sha256-hmac`), IPsec Profile.
  - `Tunnel12` (HQ `172.16.12.1/30` <-> Hà Nội `172.16.12.2/30` | IPv6 `2001:DB8:CAFE:12::/64`), gán `tunnel protection ipsec profile ...`.
  - `Tunnel13` (HQ `172.16.13.1/30` <-> Đà Nẵng `172.16.13.2/30` | IPv6 `2001:DB8:CAFE:13::/64`), gán `tunnel protection ipsec profile ...`.
  - Chú ý điều chỉnh `ip mtu 1400` và `ip tcp adjust-mss 1360` để chống phân mảnh gói tin (Fragmentation).

### 3. Step 8: Quality of Service (QoS - LLQ)
- [ ] **Class-Map phân loại lưu lượng:**
  - `CM-VOIP`: match `dscp ef` (VoIP - Ưu tiên độ trễ cực thấp).
  - `CM-VIDEO`: match `dscp af31` (Video Conference).
- [ ] **Policy-Map ưu tiên hàng đợi (LLQ):**
  - `PM-WAN-QOS`: `class CM-VOIP` dùng `priority percent 30` (hoặc bandwidth cố định); `class CM-VIDEO` dùng `bandwidth percent 20`; `class class-default` dùng `fair-queue`.
- [ ] **Áp dụng lên cổng WAN:** Gắn `service-policy output PM-WAN-QOS` lên giao diện WAN (`Gi0/0`) / Tunnel của `HCMC-EDGE-RTR01`, `HANOI-RND-RTR01`, `DANANG-LOG-RTR01`.

---

## Cách nộp bài khi hoàn thành
```bash
git add Draft_Modules/member2_routing_wan_qos/
git commit -m "feat(routing-wan-qos): complete Step 5, Step 6 & Step 8 configurations"
git push origin HEAD
```
