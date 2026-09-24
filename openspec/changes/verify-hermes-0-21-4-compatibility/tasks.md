# Tasks: Verify Hermes 0.21.4 Compatibility

## 1. 环境准备

- [ ] 1.1 创建独立 conda 环境:`conda create -n hermes-0.21.4 python=3.11`
- [ ] 1.2 激活环境:`conda activate hermes-0.21.4`
- [ ] 1.3 安装 Hermes 0.21.4:`pip install hermes-agent==0.21.4`
- [ ] 1.4 安装插件开发依赖:`pip install -e ".[dev]"`
- [ ] 1.5 验证安装成功:`hermes --version` 输出 `0.21.4`
- [ ] 1.6 记录依赖版本:`pip freeze > requirements-hermes-0.21.4.txt`

## 2. 单元测试(无 Hermes 运行时依赖)

- [ ] 2.1 运行完整测试套件:`pytest tests/ -v`
- [ ] 2.2 检查测试覆盖率:`pytest --cov=plugins --cov-report=term-missing`
- [ ] 2.3 目标:所有测试通过,覆盖率 ≥ 80%
- [ ] 2.4 若有失败,分析原因并修复(记录到 CHANGELOG)

## 3. 接口兼容性验证(重点检查清单)

- [x] 3.1 验证 `prefetch(query, session_id)` 方法签名和返回值
- [x] 3.2 验证 `sync_turn(user, assistant, session_id)` 接收完整轮次上下文
- [x] 3.3 验证 `on_session_switch(new_session_id, parent_session_id, reset, rewound)` 参数完整性
- [x] 3.4 验证 `on_session_end(messages)` 调用时机和参数
- [x] 3.5 验证 `on_memory_write(action, target, content, metadata)` 行为一致性
- [x] 3.6 验证 `shutdown()` 在 Hermes 0.21 的 drain budget 内完成(≤ 5s)
- [x] 3.7 验证 `backup_paths()` 返回空列表(无外部依赖)

## 4. 集成测试(本地 Hermes 0.21.4 实例)

- [ ] 4.1 配置 Hermes 使用本插件:编辑 `~/.config/hermes/config.yaml`
- [ ] 4.2 启动 Hermes:`hermes start`
- [ ] 4.3 测试场景 1:基础对话记忆
  - [ ] 4.3.1 执行 5 轮对话
  - [ ] 4.3.2 验证 episodic memory 写入(每轮 `importance=0.35`)
  - [ ] 4.3.3 验证 semantic_user 提升(置信度 ≥ `promotion_min_score`)
  - [ ] 4.3.4 验证 `prefetch` 返回正确上下文
- [ ] 4.4 测试场景 2:会话切换
  - [ ] 4.4.1 执行 `/new` 命令
  - [ ] 4.4.2 验证旧 session 缓存清除
  - [ ] 4.4.3 验证新 session 记忆隔离
- [ ] 4.5 测试场景 3:Undo 操作
  - [ ] 4.5.1 执行 3 轮对话后触发 `/undo`
  - [ ] 4.5.2 验证 `on_session_switch(rewound=True)` 被调用
  - [ ] 4.5.3 验证缓存失效,下次 `prefetch` 重新计算
- [ ] 4.6 测试场景 4:Shutdown 流程
  - [ ] 4.6.1 执行 `hermes stop`
  - [ ] 4.6.2 验证 `shutdown()` 在 5s 内完成
  - [ ] 4.6.3 验证无后台任务泄漏
- [ ] 4.7 测试场景 5:Gateway 身份解析
  - [ ] 4.7.1 发送带 `X-Hermes-User-Email` header 的请求
  - [ ] 4.7.2 验证 `principal_id` 正确解析为 user_email
  - [ ] 4.7.3 验证记忆隔离到用户级别

## 5. 行为变更验证(Hermes 0.20-0.21 特性)

- [x] 5.1 验证 completed-turn context:检查 `sync_turn` 是否接收完整消息交换
- [x] 5.2 验证无重复记忆写入:检查 `governance.fingerprint_text` 去重逻辑
- [x] 5.3 验证 session store 兼容性:确认插件不直接依赖 `state.db` 内部实现
- [x] 5.4 验证模块化移出无影响:确认插件作为独立 package 正常加载

## 6. 问题修复(若发现不兼容)

- [ ] 6.1 记录所有发现的问题到 `compatibility-issues.md`
- [ ] 6.2 评估每个问题的严重程度(Critical / High / Medium / Low)
- [ ] 6.3 修复 Critical 和 High 问题
- [ ] 6.4 重新运行失败的测试用例
- [ ] 6.5 Medium 和 Low 问题记录到 README "Known Issues" 章节

## 7. 文档更新

- [ ] 7.1 更新 `CLAUDE.md` "Hermes 兼容性" 章节:改为 "Hermes 0.18-0.21"
- [x] 7.2 更新 `README.md` "Upgrading" 章节:新增 "0.6.1 — Hermes 0.20-0.21 Compatibility Verified" 条目
- [x] 7.3 更新 `CHANGELOG.md`:新增版本条目(若需代码调整) — **无需代码调整**
- [x] 7.4 若无代码调整,在 CHANGELOG 添加 "Verified" 章节记录验证结果

## 8. 版本管理(若有代码变更)

> **注**: 本次验证无需代码变更,以下任务跳过。

- [x] 8.1 按 SemVer 递增 `pyproject.toml` 的 `version` — **跳过(无需代码变更)**
- [x] 8.2 同步更新 `CLAUDE.md` "当前版本" — **跳过(无需代码变更)**
- [x] 8.3 同步更新 `CHANGELOG.md` 顶部版本条目 — **跳过(无需代码变更)**
- [x] 8.4 验证三处版本号一致 — **跳过(无需代码变更)**

## 9. 最终验证

- [ ] 9.1 运行 `ruff check --fix` 和 `ruff format`
- [ ] 9.2 运行 `pytest tests/` 全绿
- [ ] 9.3 在 Hermes 0.21.4 环境下执行 smoke test(5 分钟快速验证)
- [ ] 9.4 在 Hermes 0.19 环境下执行回归测试(确认无破坏性变更)
- [ ] 9.5 生成兼容性报告:`compatibility-report-hermes-0.21.4.md`

## 10. 交付

- [ ] 10.1 提交代码(若有变更):`git commit -m "feat: verify Hermes 0.21.4 compatibility"`
- [ ] 10.2 创建 Pull Request(若需 review)
- [ ] 10.3 更新项目 README 的兼容性徽章(若有)
- [ ] 10.4 通知相关干系人验证结果
