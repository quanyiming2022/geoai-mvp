# AOI / Visual Prompt 名称与描述编辑

2026-09-11，本地 macOS arm64，开发分支 feat/p9-real-model-worker。

入口：左侧 AOI / 视觉样例清单 → 名称右侧 ⋯ → 重命名 / 编辑描述。小型弹窗按需打开，未修改禁用保存，取消不写入。右侧属性只展示描述，无常驻编辑表单。定位、样例下载为已有操作，不添加不安全删除。

API PATCH 只接受名称、描述及对应旧值，拒绝额外几何/来源字段。名称 1–120 字符、描述最多 2000 字符，可清空。旧值比较防止并发覆盖。请求沿用认证调用方，数据库 UPDATE 由现有 owner/editor RLS 与 name/description 列权限共同限制；geometry、project_id、对象文件和 job 引用不变。

验证：80 后端测试、3 前端测试、typecheck、lint、Ruff、Docker API/Web 生产构建 PASS。隔离真实验收验证两类对象改名/描述/恢复、冲突、viewer/outsider 拒绝、editor 改名、直接 SQL RLS、geometry 不可更新，编辑后完整对象恢复一致。P9C Mock 全流程回归（包含 P8 栅格/样例/AOI/结果/审核/导出）PASS。P9B 真实 GPU 不包含在本次通过范围。

初次描述迁移被自动审批拒绝；只读查询 pg_policies 证明 USING/WITH CHECK 限定 owner/editor 后，重新审查批准迁移，未绕过权限。

浏览器：AOI 清单菜单含定位/重命名/编辑描述，描述弹窗正常，未修改保存禁用，sameMap=true，取消关闭。截图保存在忽略目录 `artifacts/object-actions-menu.png` 和 `artifacts/object-description-dialog.png`。15 个容器 healthy，临时 P9C 项目剩余 0。
