# Devin Desktop 简体中文语言包

为 Windows 版 Devin Desktop **3.12.17** 新增可选择的「简体中文」。在个人偏好设置里可以随时切换 English 和简体中文，选择会在重新启动后保留。

![Devin 的界面语言下拉菜单，English 和简体中文并列](docs/language-picker.jpg)

## 安装

1. 安装 Windows 版 Devin Desktop 3.12.17 和 Python 3.10 或更高版本。当前适配的编辑器内核为 1.141.2。
2. 下载 [发布包](https://github.com/okht/devin-desktop-zh-cn/releases/latest)，解压，保存当前工作并完全退出 Devin。
3. 在解压目录打开终端，运行以下命令。首次安装时，工具会调用 Devin 自带的扩展安装器获取微软简体中文扩展 1.131.0。

   ```powershell
   .\Devin-ZH.cmd apply
   ```

4. 重新打开 Devin，在「Settings → Preferences → Appearance → Display language」选择「简体中文」。切回英文时，在「设置 → 偏好设置 → 外观 → 界面语言」选择「English」。如出现重启提示，确认后编辑器菜单会同步。

也可以直接运行 `py -3 devin_zh.py apply`。自定义安装目录可附加 `--app "D:\Apps\Devin\resources\app"`。脚本会核对构建和原文件的 SHA-256，遇到其他版本或未经识别的修改会显示具体文件。

## 检查与恢复

```powershell
.\Devin-ZH.cmd status
.\Devin-ZH.cmd restore
```

恢复前请保存工作并退出 Devin。恢复命令会从本机备份还原应用文件和微软扩展的原版词典。微软简体中文扩展保留在扩展列表里，可单独卸载。安装和恢复均保留当前界面语言偏好。

## 翻译范围

| 界面 | 示例 |
| --- | --- |
| 会话和工具活动 | 「已运行」「已思考 4 秒」「已发起代码扫描」「正在执行操作」 |
| Git 提交和代码审查 | 区分提交作者、提交者与共同署名顺序，PR 统一使用「拉取请求」 |
| 本地设置和代码补全 | 自动继续、代码检查、行内提示、按 Tab 导入与跳转 |
| DeepWiki 和会话菜单 | 生成投入程度、更新频率、语言名称、定时运行与更改父会话 |

会话主词典有 23,552 个条目，代码审查词典有 1,341 个条目。编辑器生成 27,543 条界面消息。命令参数、文件路径和用户的会话内容照原样显示。DeepWiki 的「生成语言」用于配置知识库内容，原版始终勾选英语。

发布前，已在干净的原版副本上通过 Devin 安装微软扩展，核对了 330 个安装目标的哈希，验证了重复安装、恢复和再次恢复。重建后的界面资源通过了 English 与简体中文双向切换、重新加载后的语言选择以及 166 组工具活动状态检查。此版本仅在 Windows 上验证。

## 仓库内容

- `locales/` 保存中文词典、编辑器补充词条和内置扩展的显示字段。360 个沿用原文的会话词条在安装时从用户自己的 Devin 中读取。
- `patches/` 保存本构建的界面修改。每行记录原文件字符位置、替换长度和新增内容。嵌入词典的位置引用同一份中文词典。
- `manifest.json` 记录支持的构建，以及安装前后各文件的 SHA-256。原版程序、个人启动配置和聊天记录均不随发布包分发。

维护译文时，可在原版安装和微软语言包上运行以下检查。它在内存中重建所有目标并核对哈希。修改词条后可附加 `--update-hashes` 更新仓库里的发布清单。

```powershell
py -3 tools/check_build.py --app "D:\Apps\Devin\resources\app" --extensions "$env:USERPROFILE\.devin\extensions"
```

会话及界面译文参考了两个社区项目，编辑器基础词典使用微软简体中文扩展。各来源与许可见 [第三方声明](THIRD_PARTY_NOTICES.md)。
