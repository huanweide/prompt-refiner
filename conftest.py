"""pytest 全局配置：保证导入的始终是仓库内的源码。

为什么要这个文件
----------------
项目测试原来依赖 `pip install -e .` 才能 import 到 promptrefiner。
这带来一个隐蔽的坑：一旦环境里装的是**别处的**同名包（比如另一份
development checkout），`pytest` 会静默测到那份源码上 —— 测试全绿，
但绿的是别人家的代码，本机改动一个都没被测到。本机就真实发生过：
环境里有一个 editable 安装指向另一份目录，结果 sys.path 解析到了那里。

解法是把仓库内的 src 顶到 sys.path 最前面，让「仓库内的源码」永远优先。
这样两种情况都成立：
  - 没装过包，直接 clone 下来跑 pytest 也能跑；
  - 装了别处的同名包，也不会再悄悄测错地方。
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = str(Path(__file__).resolve().parent / "src")
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)
