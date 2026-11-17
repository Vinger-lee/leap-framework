# A4 打印工作流

1. 用 `get_print_materials(session_id, node_id)` 查找已保存版本。正式导出要求
   当前有效证据和预审版本。历史稿可读取，缺有效版本时先核对校准与教学包。
   准备交付时读取一次 `get_teaching_delivery_policy()`。
2. 从 `get_grounding_sources(session_id, include_lesson=True)` 取 `.lesson.print_draft`，
   独立核对讲义、题目和答案。以原值用 `save_print_materials(...)` 保存，带实际
   `session_id`、`node_id` 和教学包 `package_id`，可调整方向和边距。
3. 检查 `uncovered_point_ids`，实测 PDF 的层级、配色、公式和分页。新编稿只作待审草稿。
4. 交付整套课程时用 `export_print_pdf(session_id, node_id, package_id=...)`，默认按课程名建目录，
   内含教学 HTML、讲义册、题目册、答案与解析、合订册。用回执里的 `output_directory`、`html_path`
   和 `pdf_paths` 交付文件。用户可指定版式、方向或边距。没有 Chromium 时按错误回执引导安装，
   同时可使用已准备的独立打印 HTML 在浏览器离线打印。
5. 页面发来 PDF 请求且缺稿时，处理回执里的 `next_call`，登记预审版后重试同一导出条件，
   把最终 PDF 回执映射到原 `call_id`。离线课程包使用 `html_directory` 写出独立文件，
   让四个页面入口指向对应 HTML。保存和渲染成功只确认技术结构，Agent 负责图文和题目内容复核。
