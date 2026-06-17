# Codex Project Workspace

这个工作区现在按“一个项目一个文件夹”整理到了 `projects/` 目录下：

- [AI Weekly Digest](/Users/youngkit/Documents/codex_project/projects/ai-weekly-digest/README.md)
- [Job Tracker](/Users/youngkit/Documents/codex_project/projects/job-tracker/README.md)

建议以后新项目都按下面的结构创建：

```text
projects/
  your-project-name/
    README.md
    requirements.txt
    .env.example
    src-or-scripts
    docs-or-data
```

根目录只保留工作区级文件，例如：

- `README.md`
- `.gitignore`
- `.github/workflows/`
- 共享的本地虚拟环境或兼容性配置
