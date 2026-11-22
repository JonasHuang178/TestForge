# TestForge

從 markdown 測試計畫產生 C++ 測試程式碼。

```
markdown 計畫  ->  IR (TestCase/TestStep)  ->  code fragments  ->  組裝後的 C++
```

真正重要的契約只有兩個：**IR**（一份計畫的語意是什麼）和 **device**（某個目標如何把那個語意變成檔案）。其餘部分都是可替換的。

## 快速開始

需要 Python 3.11 以上。

**macOS / Linux**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
testforge serve
```

**Windows（PowerShell）**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
testforge serve
```

若 PowerShell 擋下啟用指令稿，先執行一次
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`。
cmd.exe 的啟用指令是 `.venv\Scripts\activate.bat`。

然後瀏覽器開 **http://127.0.0.1:8000/**。這是給使用者操作的頁面：貼上計畫、即時看到解析結果、產生程式碼、下載。

不想安裝也可以，只要相依套件在就能直接跑原始碼：

```bash
PYTHONPATH=src python3 -m uvicorn testforge.api.app:app     # macOS / Linux
```
```powershell
$env:PYTHONPATH = "src"; py -m uvicorn testforge.api.app:app  # Windows
```

命令列同樣能做完整流程：

```bash
testforge devices                                              # 有哪些 device
testforge parse  devices/simple_cpp/example_plan.md \
    --device simple_cpp                                        # 讀到了什麼
testforge generate devices/simple_cpp/example_plan.md \
    --device simple_cpp -o ./out                               # 寫出檔案
```

對同一個 `-o` 目錄再執行一次 `generate` 就是原地重新生成：只有 anchor 標記之間的區塊會被重寫，你在標記外手寫的任何東西都會保留。

## 設計準則

**確定性。** 相同的輸入產生 byte 級完全相同的輸出。產生的程式碼裡沒有時間戳、沒有隨機 id。golden file 測試依賴這一點；把產生的檔案 commit 進版控後，能不能看懂 `git diff` 也依賴這一點。重新生成時也會**保留檔案原有的換行字元**——否則 Windows 上的 CRLF 檔案每次都會被改成 LF，diff 顯示整檔都變了。

**用 diagnostics，不要用錯誤。** 測試計畫是人手寫的，一定會髒。可恢復的問題會放在 `diagnostics` 陣列裡隨 HTTP 200 回傳，讓作者一次看到所有問題。只有「完全產生不出任何可用 case」的計畫才回 4xx——而且它的 response body 帶著同樣結構的 `diagnostics`，所以前端一份 render 程式碼就能處理兩種情況。請根據 `code` 判斷，絕對不要根據 `message`。

**無狀態。** 請求之間不保存任何東西。要重新生成某個檔案，客戶端把目前的內容放在 `existing_files` 送上來，拿回只有 anchor 區塊被重寫的版本。狀態留在持有檔案的那一方。

**分層方向。** `web/`、`api/` 和 `cli.py` 都依賴 `service`，彼此互不依賴。web 層直接呼叫 `service`，**絕不**透過 HTTP 回頭呼叫自己的 API——那會多一次序列化、多一個失敗模式，而且 debug 時 stack trace 會斷掉。

**DTO 不等於 IR。** `api/schemas/` 是對外公布的契約；`core/models.py` 是內部的，可以自由演進。`api/mappers.py` 是唯一同時知道兩邊的地方。

## 專案結構

```
src/testforge/
  core/              純邏輯，零 web 依賴
    models.py        IR：TestCase, TestStep, GeneratedArtifact
    parser.py        markdown -> IR，走 markdown-it 的 token stream
    assembler.py     anchor 注入、換行保留
  device_api.py      device.py 會 import 的公開介面
  devices/
    python_device.py device.py 的載入與契約檢查
    registry.py      device 探索與查找
  service.py         GenerationService：唯一的 orchestrator
  web/               伺服器渲染的操作頁面（Jinja2 + 原生 JS，零前端依賴）
  api/               FastAPI：schemas、routers、mappers、錯誤映射
  cli.py             第三個消費端，用來確保 core 真的與 web 無關
```

## Web 介面

```bash
testforge serve            # 預設 127.0.0.1:8000
testforge serve --port 8080 --host 0.0.0.0
```

| 路徑 | 內容 |
|---|---|
| `/` | 操作頁面 |
| `/docs` | REST API 的互動式文件 |

頁面分三區：左邊貼上或開啟 markdown，右邊即時顯示偵測到的 case、步驟與 diagnostics（邊打字邊更新），下方顯示產生的檔案，可切換分頁、下載單檔或 zip。「進階」可覆寫步驟標題層級與命名規則。

**零前端依賴。** 沒有 npm、沒有建置流程、沒有 CDN——伺服器渲染 HTML 片段，約 260 行原生 JS，語法高亮是自己寫的。裝置測試常在隔離網路上進行，從 CDN 載入資源會讓工具在沒有外網時直接壞掉。

**下載是重新生成而不是快取。** 因為生成是確定性的，重跑的結果與畫面上顯示的完全一致，伺服器也就不需要保存任何東西。

## REST API

base path 是 `/api/v1`，互動式文件在 `/docs`。

| Method | Path | 用途 |
|---|---|---|
| GET | `/health` | 存活狀態與 device 數量 |
| GET | `/devices` | 列出所有 device |
| GET | `/devices/{id}` | anchor、命名規則、輸出檔名樣式 |
| POST | `/parse` | 計畫 -> IR + diagnostics，不需要 device，不產生程式碼 |
| POST | `/generations` | 計畫 + device -> artifacts |

`/parse` 獨立存在，是為了讓 UI 能在使用者邊打字時預覽步驟，也為了讓格式錯誤在還沒選 device 之前就浮現。

`POST /generations` 用的是複數名詞而不是 `/generate`，因為被建立的東西概念上就是一次「generation」。這樣留了兩條後路：日後若加上編譯檢查而變慢，可以改回 `202` + 輪詢；日後若要持久化結果，可以直接加上 `GET /generations/{id}`——兩者都不需要改動 URL。

`generation_id` 只是給 log 用的 correlation id。系統不保存任何東西，這個 id 無法用來查詢。

### 回應的表示形式

```
POST /api/v1/generations?format=json   application/json  （預設）
POST /api/v1/generations?format=zip    application/zip   + Content-Disposition
POST /api/v1/generations?format=file   text/plain        僅限單一 artifact
```

用 query parameter 而不是 `Accept` 做 content negotiation，是因為一般的 HTML form 沒辦法設定 `Accept`；這樣一個單純的 form post 就能觸發瀏覽器下載，完全不需要 JavaScript。

### 狀態碼

| 狀態碼 | 意義 |
|---|---|
| 400 | request body 不符合 schema，或命名 pattern 有誤 |
| 404 | `device_id` 不存在 |
| 413 | `source` 超過大小上限 |
| 422 | 計畫產生不出可用的 case，或 `existing_files` 缺少 anchor |
| 500 | device 模組或模板有問題——這是我們的錯，細節寫進 log 而不回傳 |

anchor 的問題回 422 而不是 409：它的本質是「你給的這份輸入我處理不了」，不是客戶端該重試的併發衝突。

每一個 4xx / 5xx 的 body 都是同一個 envelope：

```json
{
  "error": { "code": "device_not_found", "message": "...", "details": {} },
  "diagnostics": []
}
```

## 計畫格式

標題層級與 case 所在的區段都由 device 決定，所以你的團隊不必改既有的文件排版。以下是 `simple_cpp` 預期的格式（完整版見 `devices/simple_cpp/example_plan.md`）：

```markdown
# Console App Test Plan

## Purpose

這一段不會被讀取，修訂紀錄、環境說明都可以安心放這裡。

## Test Case List

### print all info

#### Step 1 Print the build version

Call the version helper and write it to stdout.

**Expected:** A non-empty version string is printed.

#### Step 2 Print the device id

Read the id from EEPROM.
```

* **`## Test Case List`** 是裝 case 的區段。device 用 `CASE_SECTION` 指定它之後，**只有這個區段裡面**的標題會被當成 test case——上面的 `## Purpose`、`## Environment` 連同它們的子標題都會被忽略。不設定 `CASE_SECTION` 的話，整份文件都會被掃描。
* **`### <名稱>`** 開始一個 test case（層級由 `CASE_HEADING_LEVEL` 決定）。
* **`#### Step N <標題>`** 開始一個步驟（層級由 `STEP_HEADING_LEVEL` 決定）。數字後面接空格或 `:`、`.`、`-` 都可以。有 `Step` 這個字時數字後面只有空格也行；沒有 `Step` 時必須有分隔符號，否則像「2024 annual check」這種標題會被誤判成第 2024 步。
* 步驟一律以**出現位置**編號。標題裡寫的數字若與位置不符會發出 `step.index_mismatch`，不會默默重新編號。
* `**Expected:**`、`Expected:`、`Expected result:`、`預期結果：` 都能開啟一段預期結果。
* 緊接在 case 標題下的 bullet list 是 metadata（`Key: Value`）。
* 步驟正文保留原始 markdown，包含 fenced code block。fence 裡的 `#` 絕不會被誤認成標題。

這些都由 `device.py` 設定，所以另一個 device 可以用完全不同的慣例，共用同一個解析器。

## 新增一個 device

一個 device 就是一個資料夾，裡面放**一個 `device.py`** 加上它要填寫的 `.h` / `.cpp`（或 `.c` / `.h`，由你決定）。`device.py` 是**你自己寫的**，每個 device 的產生規則都寫在裡面。

```
devices/
  simple_cpp/
    device.py                 # 你寫的規則：命名、輸出哪些檔、填什麼內容
    main.cpp                  # 你的真實模板，不含任何標記
    example_plan.md           # 這個 device 的範例計畫
  my_board/
    ...
```

複製 `devices/simple_cpp/` 改名就能新增 device，資料夾名稱要和 `device.py` 裡的 `ID` 一致。

範例計畫放在 device 資料夾裡，由 `EXAMPLE_PLAN` 指定。web 頁面的「載入範例」會載入**當前選到的 device** 的那一份——一份為某個 device 寫的計畫，在另一個 device 的標題慣例下會解析不出東西，所以範例必須跟著 device 走。資料夾名稱必須和 `device.py` 裡的 `ID` 一致。TestForge 會從套件內建的 device、專案根目錄的 `./devices/`，以及 `TESTFORGE_DEVICE_PATH` 載入；後面的會蓋掉前面同名的。

### device.py 的契約

必須定義四樣東西：

```python
ID = "my_board"            # 與資料夾同名
NAME = "My Board"

def step_function_name(step):
    """一個步驟 -> 一個 C 函式名稱。這就是你的命名規則。"""
    return identifier(f"TestStep_{step.index:02d}_{pascal(step.title)}")

# 以下兩者**擇一**
def build(case):
    """每個 case 產生自己的檔案時用這個。"""
    return [output("test_x.cpp", template="test_case.cpp", anchors={...})]

def build_all(cases):
    """所有 case 寫進同一個檔案時用這個。"""
    return [output("test_main.cpp", content=..., anchors={...})]
```

`build` 和 `build_all` **必須且只能定義一個**，載入時會檢查。選錯會壞：若所有 case 共用一個檔案卻用 `build(case)`，每個 case 都會覆寫同一塊 anchor 區域，只有最後一個留下來。

可選的有 `DESCRIPTION`、`VERSION`、`CASE_HEADING_LEVEL`、`STEP_HEADING_LEVEL`、`CASE_SECTION`、`SECTION_HEADING_LEVEL`、`ANCHOR_BEGIN`、`ANCHOR_END`、`EXAMPLE_PLAN`。

`output()` 的三個部分：

| 參數 | 意義 |
|---|---|
| `path` | 要產生的檔名，由你從 `case` 算出來 |
| `template` | 同資料夾下的範本檔，**只在輸出檔還不存在時**使用 |
| `content` | 直接給定骨架內容，取代 `template`。模板沒有 anchor 標記、需要由 `device.py` 自己插入時用這個 |
| `anchors` | anchor 名稱 -> 要放進該區塊的程式碼 |
| `**variables` | 範本裡的 `@@NAME@@` placeholder，只在建立時替換 |

範本用 `@@NAME@@` 而不是大括號，因為 C/C++ 本來就充滿大括號。

`case` 和 `step` 可用的欄位，以及 `pascal` / `snake` / `cstr` / `comment` / `guard` / `identifier` 這些輔助函式，都定義在 `src/testforge/device_api.py`，有完整 docstring。

### 框架仍然保證的事

不論你的 `device.py` 怎麼寫：

- **只有 anchor 之間的區塊會被重寫** —— 其餘手寫的程式碼永遠保留
- **檔案原有的換行字元會保留** —— CRLF 不會被改成 LF
- **相同輸入產生 byte 級相同的輸出**
- 計畫的解析方式對所有 device 一致

所以你只要負責「產生什麼」，不必處理「怎麼安全地寫回檔案」。

### 自訂 anchor 標記

預設標記是 `// === TESTFORGE:{name}:BEGIN ===`。產生舊式 C（`//` 不是合法註解）時，在 `device.py` 裡覆寫：

```python
ANCHOR_BEGIN = "/* === TESTFORGE:{name}:BEGIN === */"
ANCHOR_END   = "/* === TESTFORGE:{name}:END === */"
```

### 模板不含標記時

`simple_cpp/main.cpp` 是一份乾淨的檔案：

```cpp
#include <iostream>

int main()
{
    return 0;
}
```

`device.py` 在建立輸出檔時自己插入兩組標記——一組放在 `int main` 之前（test case 函式進這裡），一組放在 `main` 裡面（呼叫進這裡）。這樣這份 `main.cpp` 仍然是一個可以打開、可以編譯、可以單獨理解的檔案，而不是一份佈滿註解標記的樣板。

### 試一下

```bash
testforge generate devices/simple_cpp/example_plan.md --device simple_cpp -o ./out
cd out && g++ -std=c++17 -Wall -Wextra -Werror -o runner test_main.cpp && ./runner
```

## 測試

```bash
pytest                                              # 全部
UPDATE_GOLDEN=1 pytest tests/test_golden.py         # 接受模板的變更
```

三個層次：單元測試負責邊界情況（命名、解析、anchor），golden file 負責使用者實際拿到的東西，API 測試負責契約——狀態碼、error envelope，以及重新生成的 round trip。
