# THÀNH VIÊN 1: HƯỚNG DẪN LÀM BÀI MẢNG SWITCHING, STP, LACP, HSRP & DHCP (STEP 3 & STEP 4)

- **Nhánh Git làm việc:** `feature/switching-dhcp`
- **File soạn thảo chính:** `Draft_Modules/member1_switching_dhcp/member1_switching_dhcp_draft.cfg`
- **Tài liệu tham chiếu bắt buộc:** [`Specs/IP_Addressing_Schema.md`](../../Specs/IP_Addressing_Schema.md)

> **Lưu ý Zero-Conflict:** Tuyệt đối giữ nguyên toàn bộ Hostname, số hiệu VLAN, tên cổng 16-port trên Switch `vIOS-L2` (`Gi0/0-3`, `Gi1/0-3`, `Gi2/0-3`, `Gi3/0-3`) và địa chỉ IPv4/IPv6 đã chốt trong `Specs/IP_Addressing_Schema.md` để Leader ghép bài không bị xung đột.

---

## Danh sách công việc cần hoàn thành (Checklist theo Rubric & Pre-Submission Checklist)

### 1. Step 3: Layer 2 Infrastructure & Spanning Tree Protocol (STP)
- [ ] **Khởi tạo VLAN chuẩn toàn hệ thống** trên tất cả Switch (`HCMC-DIST-SW01`, `HCMC-DIST-SW02`, `HCMC-CORE-SW01`, `HANOI-RND-SW01`, `HANOI-RND-SW02`, `DANANG-LOG-SW01`):
  - `VLAN 10`: `EXEC_FINANCE` (HQ)
  - `VLAN 20`: `RND_ENGINEERING` (HQ & HN)
  - `VLAN 30`: `LOGISTICS_OPS` (ĐN)
  - `VLAN 50`: `GUEST_WIFI` (HN)
  - `VLAN 99`: `MANAGEMENT` (3 miền)
  - `VLAN 999`: `BLACKHOLE` (Cô lập toàn bộ cổng thừa và `shutdown`)
- [ ] **802.1Q Trunking:** Cấu hình `switchport trunk encapsulation dot1q` (trên L3 Switch) và `switchport mode trunk` cho các đường nối liên Switch (`Gi1/0` trên DIST <-> `Gi0/1`, `Gi0/2` trên CORE) và từ Switch lên Router (HN & ĐN: `Gi0/1`).
- [ ] **Access Ports & PortFast:** Gán đúng dải cổng Access (`Gi0/0`, `Gi0/3`, `Gi1/0-1/3` tùy thiết bị) vào VLAN tương ứng theo `Specs/IP_Addressing_Schema.md`, bật `spanning-tree portfast` và `bpduguard enable` cho các cổng Access PC/AP. Đưa tất cả các cổng dư (`Gi1/2`, `Gi2/0-3`, `Gi3/0-3`...) vào `VLAN 999` và `shutdown`.
- [ ] **LACP EtherChannel (`Port-channel 1`):** Bó dây dùng chuẩn mở LACP (`channel-group 1 mode active`) trên cặp `Gi0/2` & `Gi0/3` giữa:
  - `HCMC-DIST-SW01` <-> `HCMC-DIST-SW02`
  - `HANOI-RND-SW01` <-> `HANOI-RND-SW02`
- [ ] **Spanning Tree (`Rapid-PVST+`):** Bật `spanning-tree mode rapid-pvst` trên mọi Switch:
  - Tại HQ: Ép `HCMC-DIST-SW01` làm **Root Primary** (`spanning-tree vlan 10,20,99 root primary`), `HCMC-DIST-SW02` làm **Root Secondary** (`root secondary`).
  - Tại HN: Ép `HANOI-RND-SW01` làm **Root Primary**.

### 2. Step 4: First Hop Redundancy (HSRP) & Centralized DHCP Services
- [ ] **HSRP tại HQ (`HCMC-DIST-SW01` & `HCMC-DIST-SW02`):**
  - `Vlan 10`: VIP `10.10.10.1` (`SW01`: `.2`, `priority 110`, `preempt`; `SW02`: `.3`, `priority 100`).
  - `Vlan 20`: VIP `10.10.20.1` (`SW01`: `.2`, `priority 110`, `preempt`; `SW02`: `.3`, `priority 100`).
  - `Vlan 99`: VIP `192.168.1.1` (`SW01`: `.2`, `priority 110`, `preempt`; `SW02`: `.3`, `priority 100`).
  - Bật `ipv6 address` tương ứng trên từng SVI Dual-Stack.
- [ ] **DHCP Tập trung & DHCP Relay (`ip helper-address 10.10.10.50`):**
  - Cấu hình `ip helper-address 10.10.10.50` tại:
    - `HCMC-DIST-SW01` & `SW02`: `interface Vlan 20` (và `Vlan 99` nếu cấp động).
    - `HANOI-RND-RTR01`: `interface Gi0/1.20` và `Gi0/1.50`.
    - `DANANG-LOG-RTR01`: `interface Gi0/1.30`.
  - Viết cấu hình các DHCP Pool cho máy chủ DHCP tập trung (`10.10.10.50`) hoặc Pool dự phòng với DNS `10.10.10.50` / `8.8.8.8` và `ip dhcp excluded-address`.
- [ ] **Default Gateway cho Switch Layer 2 (để SSH từ HQ ở Step 9):**
  - `HCMC-CORE-SW01`: `ip default-gateway 192.168.1.1` (`Vlan 99`: `192.168.1.10/24`)
  - `HANOI-RND-SW01` & `SW02`: `ip default-gateway 192.168.2.1` (`Vlan 99`: `.10` và `.11`)
  - `DANANG-LOG-SW01`: `ip default-gateway 192.168.3.1` (`Vlan 99`: `192.168.3.10/24`)

---

## Cách nộp bài khi hoàn thành
```bash
git add Draft_Modules/member1_switching_dhcp/
git commit -m "feat(switching-dhcp): complete Step 3 & Step 4 configurations"
git push origin HEAD
```
