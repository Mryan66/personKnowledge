# macOS 自动定时复盘

本项目不内置 Python 后台守护进程。推荐使用 macOS `launchd` 触发 CLI：

- 每天 `08:30` 执行 `daily review`
- 每周一 `09:00` 执行 `weekly review`
- 每月 `1` 日 `09:30` 执行 `monthly review`

所有自动任务都通过：

```bash
python3 -m app.cli review --period <daily|weekly|monthly> --triggered-by auto
```

运行历史会被写入应用数据库中的 `review_runs` 表，Web Review 页面可直接展示最近执行记录。

## 使用前准备

1. 确认项目绝对路径，例如：`/ABSOLUTE/PATH/personKnowledge`
2. 确认 Python 绝对路径，例如：`/usr/bin/python3` 或你实际使用的虚拟环境 Python
3. 先手动验证命令可运行：

```bash
/ABSOLUTE/PATH/TO/python3 -m app.cli review --period daily --triggered-by auto
```

4. 将下面模板中的以下路径替换为你自己的绝对路径：
   - `/ABSOLUTE/PATH/personKnowledge`
   - `/ABSOLUTE/PATH/TO/python3`

## Plist 模板

### `com.personalkb.review.daily.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.personalkb.review.daily</string>

  <key>WorkingDirectory</key>
  <string>/ABSOLUTE/PATH/personKnowledge</string>

  <key>ProgramArguments</key>
  <array>
    <string>/ABSOLUTE/PATH/TO/python3</string>
    <string>-m</string>
    <string>app.cli</string>
    <string>review</string>
    <string>--period</string>
    <string>daily</string>
    <string>--triggered-by</string>
    <string>auto</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>30</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>/tmp/personalkb-review-daily.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/personalkb-review-daily.err</string>
</dict>
</plist>
```

### `com.personalkb.review.weekly.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.personalkb.review.weekly</string>

  <key>WorkingDirectory</key>
  <string>/ABSOLUTE/PATH/personKnowledge</string>

  <key>ProgramArguments</key>
  <array>
    <string>/ABSOLUTE/PATH/TO/python3</string>
    <string>-m</string>
    <string>app.cli</string>
    <string>review</string>
    <string>--period</string>
    <string>weekly</string>
    <string>--triggered-by</string>
    <string>auto</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key>
    <integer>1</integer>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>/tmp/personalkb-review-weekly.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/personalkb-review-weekly.err</string>
</dict>
</plist>
```

### `com.personalkb.review.monthly.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.personalkb.review.monthly</string>

  <key>WorkingDirectory</key>
  <string>/ABSOLUTE/PATH/personKnowledge</string>

  <key>ProgramArguments</key>
  <array>
    <string>/ABSOLUTE/PATH/TO/python3</string>
    <string>-m</string>
    <string>app.cli</string>
    <string>review</string>
    <string>--period</string>
    <string>monthly</string>
    <string>--triggered-by</string>
    <string>auto</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Day</key>
    <integer>1</integer>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>30</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>/tmp/personalkb-review-monthly.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/personalkb-review-monthly.err</string>
</dict>
</plist>
```

## 安装与加载

将对应内容保存到 `~/Library/LaunchAgents/`：

```bash
mkdir -p ~/Library/LaunchAgents
```

例如：

```bash
cp com.personalkb.review.daily.plist ~/Library/LaunchAgents/
cp com.personalkb.review.weekly.plist ~/Library/LaunchAgents/
cp com.personalkb.review.monthly.plist ~/Library/LaunchAgents/
```

加载任务：

```bash
launchctl load ~/Library/LaunchAgents/com.personalkb.review.daily.plist
launchctl load ~/Library/LaunchAgents/com.personalkb.review.weekly.plist
launchctl load ~/Library/LaunchAgents/com.personalkb.review.monthly.plist
```

如果你修改了 plist，先卸载再重新加载：

```bash
launchctl unload ~/Library/LaunchAgents/com.personalkb.review.daily.plist
launchctl load ~/Library/LaunchAgents/com.personalkb.review.daily.plist
```

## 手动触发与排查

手动触发：

```bash
launchctl start com.personalkb.review.daily
launchctl start com.personalkb.review.weekly
launchctl start com.personalkb.review.monthly
```

查看日志：

```bash
tail -f /tmp/personalkb-review-daily.log
tail -f /tmp/personalkb-review-daily.err
```

常见问题：

- `ModuleNotFoundError`：通常是 `WorkingDirectory` 不对，或 Python 环境不是项目所用环境
- 任务无输出：检查 `StandardOutPath` / `StandardErrorPath`
- Web 页面看不到运行记录：确认命令中带有 `--triggered-by auto`，并且数据库路径与 Web 使用的是同一个工作区
