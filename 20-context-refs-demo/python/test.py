"""test.py —— refs 解析 / 沙箱 / 行切片 / 渲染 单元测试，不依赖外网。"""
from __future__ import annotations

from refs import render_for_llm, resolve_refs


def t(label: str, cond: bool) -> bool:
    print(f"{'✓' if cond else '✗'} {label}")
    return cond


def main() -> None:
    passed = sum([
        # 单一 @ref
        t("single @ref resolved",
          (lambda: resolve_refs("@user.py 是啥")[0][0].error is None)()),

        # line range
        t("@path:start-end parsed",
          (lambda: resolve_refs("@api.py:5-10")[0][0].start == 5
           and resolve_refs("@api.py:5-10")[0][0].end == 10)()),

        # 沙箱：绝对路径或 ../ 不行
        t("escape ../../../etc blocked",
          (lambda: resolve_refs("@../../etc/passwd")[0][0].error is not None)()),

        # 不存在的文件
        t("nonexistent file → error",
          (lambda: resolve_refs("@nope.py")[0][0].error == "file not found")()),

        # 没 @ref 不调
        t("no @ref → empty",
          resolve_refs("纯文本问题没有引用") == ([], [])),

        # render 把 ref 拼成 <file> 块
        t("render embeds <file> block",
          "<file " in render_for_llm("@user.py", resolve_refs("@user.py")[0])),

        # render 没 ref 时不动 message
        t("render passthrough without refs",
          render_for_llm("plain msg", []) == "plain msg"),

        # 同一 ref 出现两次只读一次（dedupe）
        t("dedupe same ref",
          (lambda: len(resolve_refs("@user.py 和 @user.py")[1]) == 1)()),
    ])
    print(f"\n{passed}/8 passed")


if __name__ == "__main__":
    main()
