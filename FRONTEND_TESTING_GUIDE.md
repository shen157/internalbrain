# InternalBrain 前端验收指南

## 1. 启动项目

在项目根目录打开第一个 PowerShell：

```powershell
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

再打开第二个 PowerShell：

```powershell
$env:INTERNALBRAIN_API_URL = "http://127.0.0.1:8000"
python -m streamlit run frontend/app.py
```

## 2. 系统状态

预期结果：

- Backend 显示 Online。
- Resource Count 显示 88。
- Audit Chain 显示 Valid。
- 页面可以正常上下滚动。

## 3. 切换用户自动清空会话

1. 选择 `u001 — Alice` 并完成一次查询。
2. 将 Acting as user 改为 `u007 — Grace`。

预期结果：

- Alice 的问题、回答、引用和 Query ID 全部消失。
- 输入框中的草稿被清空。
- 页面显示 `Conversation cleared` 提示。
- 后端权限没有被修改。
- Audit Inquiry 中已经查询出的审计结果仍然保留，但普通用户看不到；切回审核员后重新显示。

## 4. 无权限与不存在资源不可区分

以 `u007 — Grace` 分别提问：

```text
What happened in the Q3 security incident?
```

```text
What is the ZXQ-991 imaginary project status?
```

两次都应显示：

```text
I could not find enough information to answer this question.
```

并且都满足：

- Context Sources 为 0。
- LLM Called 为 No。
- Abstained 为 Yes。
- 没有引用卡片。
- 不显示文件名、资源 ID、无权限或 Access Denied。

## 5. 正常授权查询

选择 `u001 — Alice`，提问：

```text
What is blocking the payment migration and when is the new cutover date?
```

预期结果：

- 返回有引用的回答。
- Context Sources 大于 0。
- LLM Called 为 Yes。
- 引用中只显示 Alice 有权访问的来源。

真实远程回答需要在 `.env` 中配置有效的 `TOKENHUB_API_KEY`。

### Alice 的 Q3 问题（相关上下文不足）

选择 `u001 — Alice`，提问：

```text
What happened in the Q3 security incident?
```

如果检索到的只是无关培训资料，远程模型会返回标准拒答。预期结果：

- 显示统一的 `I could not find enough information...`。
- LLM Called 为 Yes（因为模型判断了上下文不足）。
- Abstained 为 Yes，Context Sources 为 0，不显示无关引用。
- Safety Blocked 为 No；不能再显示 `invalid_citations`。

## 6. Live Permission Demo

先将 Acting as user 切换为审核员 `u005 — Elena (Compliance Officer)`。然后在面板中使用默认目标用户 `u004 — David` 和 `C-PAY`：

1. 点击 Revoke Access。
2. 点击 Test Access with Query，应统一拒答且来源为 0。
3. 点击 Grant Access。
4. 再次点击 Test Access with Query，应返回 C-PAY 引用。
5. 再次 Revoke，查询应恢复拒答。

预期结果：权限变更立即生效，不需要重新建立索引。

## 7. 审核员查看日志

Audit Inquiry 是审核员/管理员只读视图。

先将 Acting as user 切换为 `u005 — Elena (Compliance Officer)`。Alice、Grace、David 等普通用户不应看到 Audit Inquiry、Live Permission Demo 或 Data & Permission Sync。即使绕过前端直接请求相应 API，后端也应返回 HTTP 403。

### 查看一次查询的完整记录

1. 完成任意一次查询并复制 Security & Grounding 中的 Query ID。
2. 展开 `Audit Inquiry`。
3. 将 Query ID 粘贴到 Query ID 过滤框。
4. Event Type 选择 All。
5. 点击 Search Audit Events。

预期结果：

- Audit Chain 显示 Valid。
- 能看到该查询的 `query_received`、`input_safety`、`authorization_retrieval`、`context_assembled`、`final_response` 等事件。
- 每条日志可以展开查看原始记录。
- 哈希值在页面中被截断显示。

### 查看权限变更记录

1. Event Type 选择 `permission_change`。
2. User ID 输入目标用户，例如 `u004`。
3. Action 输入 `grant_slack_membership` 或 `revoke_slack_membership`。
4. Resource ID 输入 `C-PAY`。
5. 点击 Search Audit Events。

预期结果：

- 能看到操作人 `u005`、目标用户、资源、动作和 granted/revoked 决策。
- 日志查询不会修改任何权限或审计记录。
- 切换 Acting User 后，审核员当前看到的日志结果不会被清空。

## 8. 自动化测试

```powershell
python -m unittest tests.test_access_indistinguishability -v
python -m unittest tests.test_admin_authorization -v
python tests/frontend/test_frontend.py
python tests/frontend/test_frontend_live.py
python -m unittest tests.frontend.test_api_client -v
python tests/validate_dataset.py
python -m evaluation.test_live_permission_change
python -m evaluation.test_audit_inquiry
```

Streamlit 测试期间出现 `missing ScriptRunContext` 警告属于测试框架提示，不表示测试失败。
