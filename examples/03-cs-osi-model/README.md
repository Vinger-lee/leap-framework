---
title: OSI Model Example — English Guide
tags:
- leap/examples
- computer-science/network
aliases:
- OSI Example Guide
---

> [!info] 学习资源
> 核心：`OSI seven layers encapsulation protocols definitions beginner`
> 拓展：`OSI seven layers encapsulation protocols examples conditions`
> 进阶：`OSI seven layers encapsulation protocols proof transfer`

# Example 3 · OSI Layers, Responsibilities and Encapsulation

Language: English · [[examples/03-cs-osi-model/README_CN|中文说明]]

Open `leap-03-cs-osi-model.html` directly in a browser. The page contains all CSS, JavaScript and SVG; it needs no server, network or build step. Teaching text is in Chinese. Read [[examples/03-cs-osi-model/knowledge|the complete knowledge manuscript]] for the same lesson plus derivations, extra examples and complete solutions.

Allow approximately 35–50 minutes. Start with bits/bytes and MAC/IP/port distinctions, explore both seven-layer diagrams, place the eight cards, then follow all 13 encapsulation steps through a router. Cards name specific functions: the NIC PHY belongs to the physical layer, while the NIC as a whole also includes link functions. Ethernet framing and PHY specifications are similarly distinguished.

The worked example sends 100 bytes of HTTP data over an established TCP connection, using IPv4 without options, NAT, fragmentation, VLAN or tunneling. It shows 120-byte TCP segments, 140-byte IP datagrams and 158-byte Ethernet frames through the FCS. MAC addresses change across the router; IP addresses remain under the stated assumptions, while TTL and the IPv4 header checksum change. Physical encoding does not add a universal “H1 header.”

Practice includes function matching, concept choices, a 200-byte calculation variant, a diagnosis explanation, and a new exact layer-and-basis check after revealing the full answer. Matching supports dragging, click-to-select placement and keyboard operation. Animation controls provide play/pause, forward, backward and reset; shortcuts apply within the controls. Every submitted retry preserves its raw answer. Diagnosis explanations are collected for semantic review instead of being scored from keywords.

`window.LEAP` exposes `hydrate`, `getInteractionResult`, `peekOutbox` and `drainOutbox`. The queue preview button only displays calls; the host drains and executes them. Local assessments remain provisional. Runtime supplies mastery and evidence stages; a local completion request uses `check_advance_unit`. Identifiers: `cs.network.osi_model` / `computer-science` / `osi-model`.

Validation in `leap-03-cs-osi-model.runtime.json` covers all layer selections, drag/click placement and corrections, 13-step forward/reverse playback, router changes, retries, partial credit, semantic collection, answer confirmation, new verification and queue/output behavior. Run from the repository root:

```powershell
.venv/quality-runtime/Scripts/python.exe scripts/verify_example.py examples/03-cs-osi-model/leap-03-cs-osi-model.html
.venv/quality-runtime/Scripts/python.exe scripts/verify_example_runtime.py examples/03-cs-osi-model/leap-03-cs-osi-model.html --chromium <path-to-chromium>
```

Browser tests prove behavior and the contract, not real MCP integration or a packet capture. Search terms and authoritative RFC references are in the knowledge manuscript. See [[examples/README|the example index]] and [[docs/content-quality|content quality workflow]].

> [!note]- 复核记录
> 逐项核对条件、原始输入、推导和回执；使用新输入完成迁移，不能把答案揭示作为掌握证据。


Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/03-cs-osi-model/README_CN]] · [[examples/03-cs-osi-model/knowledge]]
