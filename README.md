# TestForge

從 markdown 測試計畫產生 C++ 測試程式碼。

```
markdown 計畫  ->  IR (TestCase/TestStep)  ->  code fragments  ->  組裝後的 C++
```

真正重要的契約只有兩個：**IR**（一份計畫的語意是什麼）和 **device manifest**（某個目標如何把那個語意變成檔案）。其餘部分都是可替換的。

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
testforge devices                                     # 可以為哪些 device 生成
testforge parse examples/sensor_init.md               # TestForge 讀到了什麼
testforge generate examples/sensor_init.md \
    --device example_device --case 1 -o ./out         # 寫出檔案
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
    models.py        IR：TestCase, TestStep, CodeFragment, GeneratedArtifact
    parser.py        markdown -> IR，走 markdown-it 的 token stream
    naming.py        步驟標題 -> C++ 識別碼
    assembler.py     基於 anchor 的程式碼注入
    templating.py    Jinja2 環境與 filter
  devices/
    manifest.py      manifest schema，載入時完整驗證
    registry.py      device 探索與查找
    builtin/         隨套件發行的 device
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
| 500 | manifest 或模板有問題——這是我們的錯，細節寫進 log 而不回傳 |

anchor 的問題回 422 而不是 409：它的本質是「你給的這份輸入我處理不了」，不是客戶端該重試的併發衝突。

每一個 4xx / 5xx 的 body 都是同一個 envelope：

```json
{
  "error": { "code": "device_not_found", "message": "...", "details": {} },
  "diagnostics": []
}
```

## 計畫格式

```markdown
# Test Case: Sensor Initialization Sequence

- ID: TC-001
- Device: example_device

這裡可以寫這個 case 的說明文字，可省略。

## Step 1: Power on the device

Drive the enable line high and wait for the regulator to settle.

**Expected:** The READY flag is asserted within 500 ms.
```

* `# Test Case: <標題>` 開始一個 case；一份文件裡放多個是沒問題的，每個 case 產生自己的 artifacts。
* 緊接在 case 標題下的 bullet list 是 metadata（`Key: Value`）。
* `## Step N: <標題>` 開始一個步驟。`Step` 和數字都可以省略；步驟一律以**出現位置**編號，寫在標題裡的數字若與位置不符會發出 `step.index_mismatch`，而不是默默重新編號。
* `Expected:`、`**Expected:**`、`Expected result:` 和 `預期結果：` 都能開啟一段預期結果。
* 步驟正文保留原始 markdown，包含 fenced code block。fence 裡面的 `#` 絕不會被誤認成標題。

標題層級可以在每個 device 裡設定，所以團隊可以沿用既有的計畫排版，不必重寫文件。

## 新增一個 device

複製 `src/testforge/devices/builtin/example_device/` 然後修改即可，不需要改任何 Python。device 也會從 `./devices/` 和 `TESTFORGE_DEVICE_PATH` 載入；後面的搜尋根目錄會覆蓋前面的，所以專案可以用自己的版本蓋掉內建 device。

```
my_device/
  manifest.yaml
  templates/
    test_case.h.j2       # 骨架，負責攜帶 anchor 標記
    test_case.cpp.j2
    step_decls.cpp.j2    # fragment，被渲染進某一個 anchor
    step_calls.cpp.j2
    step_defs.cpp.j2
```

manifest 宣告 anchor 的寫法、命名規則，以及「哪個 fragment 填進哪個檔案的哪個 anchor」。`example_device/manifest.yaml` 的開頭以註解完整記錄了可用的模板 context。每份 manifest 都在 registry 載入時驗證，所以打錯字會讓服務起不來，而不是等到某個人的第一個請求才失敗。

`example_device/support/testforge_runtime.h` 是一份參考 runtime，不參與生成。它存在的理由是讓產生的程式碼可以直接編譯並執行：

```bash
testforge generate examples/sensor_init.md --device example_device --case 1 -o /tmp/tf
cp src/testforge/devices/builtin/example_device/support/testforge_runtime.h /tmp/tf
cd /tmp/tf
# 再補一個 main()，呼叫 example_device::RunSensorInitializationSequence(ctx)
g++ -std=c++17 -Wall -Wextra -Werror -o runner main.cpp test_*.cpp
```

## 測試

```bash
pytest                                              # 全部
UPDATE_GOLDEN=1 pytest tests/test_golden.py         # 接受模板的變更
```

三個層次：單元測試負責邊界情況（命名、解析、anchor），golden file 負責使用者實際拿到的東西，API 測試負責契約——狀態碼、error envelope，以及重新生成的 round trip。
