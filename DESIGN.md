# TestForge 設計說明

這份文件寫給**將來要接手或擴充 TestForge 的人**。

README 說明「怎麼用」，這份說明「為什麼是這樣」以及「哪裡不能用」。多數設計決定背後都有一個具體理由，理由不寫下來就會在下一次重構時被當成隨意的選擇而拿掉。最後一節的「已知限制」請務必讀完再動手。

---

## 1. 這個工具要解決什麼

測試計畫由人用 markdown 寫，測試程式碼用 C/C++ 寫。兩者之間的轉換重複、機械、而且容易在計畫更新後失去同步——有人改了計畫，程式碼沒跟上，或是反過來。

TestForge 把這段轉換自動化，但**不接管整個檔案**。它只負責把計畫變成程式碼骨架，並且保證重複產生時不會破壞工程師在骨架周圍寫的任何東西。

這是整個設計的核心取捨：**寧可少做，也不能覆蓋別人的程式碼**。

---

## 2. 核心流程

```
markdown 計畫  ->  IR  ->  code fragments  ->  組裝進目標檔案
                 (解析)      (device.py)         (anchor 注入)
```

| 階段 | 負責者 | 產出 |
|---|---|---|
| 解析 | 框架（`core/parser.py`） | `TestCase` / `TestStep`（IR）+ diagnostics |
| 產生 | **你的 `device.py`** | 檔名、函式名稱、要放進每個 anchor 的程式碼字串 |
| 組裝 | 框架（`core/assembler.py`） | 寫回目標檔案，只動 anchor 之間 |

**分工是刻意的**：device 作者決定「要產生什麼」，框架決定「怎麼安全地寫回去」。安全回寫是容易寫錯的部分（換行、縮排、冪等性、保留手寫碼），不該讓每個 device 各自重寫一遍。

---

## 3. 四個不可妥協的保證

這四件事對所有 device 都成立，**不論 `device.py` 怎麼寫**。改動框架時如果發現某個改法會破壞其中一項，那個改法就是錯的。

### 3.1 只有 anchor 之間會被重寫

```cpp
// === TESTFORGE:TEST_CASES:BEGIN ===
   ← 這裡面每次重新產生都會被整段替換
// === TESTFORGE:TEST_CASES:END ===

int helper() { ... }   ← 這裡是你的，永遠不動
```

**為什麼**：產生的檔案會被 commit 進版控，工程師會在裡面加 helper、fixture、include。如果重新產生會蓋掉這些，這個工具就只能用一次。

成對標記（而非單一插入點）是冪等性的來源：重寫「兩個標記之間」永遠得到同樣結果，而「在某處插入」會累加。

### 3.2 相同輸入產生 byte 級相同的輸出

產生的程式碼裡**沒有時間戳、沒有隨機 id**。

**為什麼**：
- golden file 測試靠這一點才能存在
- 產生的檔案 commit 進版控後，`git diff` 必須只顯示真正改變的行。一個時間戳會讓每次重新產生都變成整檔變更，真正的差異就被淹沒了

zip 下載也用固定時間戳，理由相同。

### 3.3 保留檔案原有的換行字元

CRLF 的檔案重新產生後還是 CRLF，不會被改成 LF。

**為什麼**：這是 Windows 上的常態。不保留的話，每次重新產生 `git diff` 都顯示整個檔案每一行都改了——直接違反 3.2 的目的。這個 bug 真的發生過（在 Linux 上永遠不會被發現，因為本來就是 LF）。

相關：CLI 讀寫檔案時關閉了文字模式的換行轉換（`newline=""`），否則讀取時 CRLF 會先被轉成 LF，寫入時 `\n` 又被轉成 `\r\n`，兩端互相打架。

### 3.4 無狀態

伺服器在請求之間不保存任何東西。要重新產生既有檔案，客戶端把**現在的內容**放在 `existing_files` 送上來，拿回只有 anchor 區塊被重寫的版本。

**為什麼**：狀態留在持有檔案的那一方（CLI 讀本地檔案、UI 讀編輯器內容）。伺服器不必處理儲存、清理、併發、多使用者隔離。

網頁的「下載」是**重新產生**而不是取用快取——這只有在 3.2 成立時才安全，而它成立。

---

## 4. 分層與依賴方向

```
src/testforge/
  core/              純邏輯，零 web 依賴
  device_api.py      device.py 會 import 的公開介面
  devices/           device 的載入與查找
  service.py         GenerationService —— 唯一的 orchestrator
  web/               伺服器渲染的頁面
  api/               REST API
  cli.py             命令列
```

**`web/`、`api/`、`cli.py` 都依賴 `service`，彼此互不依賴。**

特別注意：**web 層直接呼叫 `service`，絕不透過 HTTP 回頭呼叫自己的 API**。繞一圈會多一次序列化、多一個失敗模式，而且 debug 時 stack trace 會斷在中間。

**`api/schemas/` 的 DTO 不等於 `core/models.py` 的 IR。** IR 是內部的、可以自由增加欄位；DTO 是對外公布的契約。`api/mappers.py` 是唯一同時知道兩邊的地方。如果讓 IR 直接當 response model，每次內部重構都會變成 breaking change。

---

## 5. Device 契約

一個 device 是一個資料夾，裡面有 `device.py` 加上它要填寫的原始碼範本。

```python
ID = "my_board"            # 必須與資料夾同名（載入時檢查）
NAME = "My Board"

def step_function_name(step):
    """一個步驟 -> 一個函式名稱。這就是你的命名規則。"""

# 以下兩者擇一，且只能定義一個
def build(case):       ...  # 每個 case 產生自己的檔案
def build_all(cases):  ...  # 所有 case 寫進同一個檔案
```

### 為什麼是 Python 而不是設定檔

早期版本用 `manifest.yaml` + Jinja2 範本，後來整個移除了。原因是**真實的 device 規則是程式邏輯，不是資料**——命名規則、要產生幾個檔案、每個 anchor 放什麼，這些差異大到 schema 描述不完。用 Python 之後，device 作者可以直接寫迴圈和條件判斷。

### 為什麼 `build` 和 `build_all` 必須擇一

`build(case)` 一次只看到一個 case。如果所有 case 要寫進同一個檔案，每個 case 都會重寫同一塊 anchor 區域，**只有最後一個留下來**——而且不會報錯，檔案看起來正常，只是少了東西。

這個 bug 真的發生過。現在載入時檢查「必須且只能定義一個」，選錯會在啟動時失敗而不是默默掉資料。

### 為什麼範本用 `@@NAME@@` 而不是大括號

C/C++ 本來就滿是大括號，用 `{}` 當 placeholder 會一直誤判。

### 範本可以沒有任何標記

`output()` 可以用 `content=` 直接給定骨架，而不是指名範本檔。`simple_cpp` 就是這樣做的：它的 `main.cpp` 是一份**乾淨的、可以單獨編譯的檔案**，`device.py` 在建立輸出檔時才自己把 anchor 標記插進去（`int main` 之前一組、`main` 裡面一組）。

這樣範本仍然是一份能打開、能編譯、能單獨理解的檔案，而不是佈滿註解標記的樣板。

### 載入時就驗證

device 在 registry 載入時就被 import 並檢查契約。**缺少必要函式、ID 與資料夾不符、import 時拋例外，都會讓服務起不來**，而不是等到某個使用者的第一個請求才失敗。

註：**device 模組會被執行**（跟 pytest 執行 `conftest.py` 一樣）。device 資料夾是專案自己的程式碼，不是不受信任的輸入，沒有沙箱。

---

## 6. 計畫格式

格式**由 device 決定**，不是全域固定的。目前支援的組合：

| 設定 | 作用 |
|---|---|
| `CASE_HEADING_LEVEL` | 哪一級標題是 test case |
| `STEP_STYLE` | `"heading"` 步驟是標題；`"line"` 步驟是 `Step N ...` 文字行 |
| `STEP_HEADING_LEVEL` | 僅 `"heading"` 模式使用 |
| `CASE_SECTION` | 只在這個區段裡找 case |
| `CASE_TABLE` | 把區段開頭的表格讀成 case 索引 |

### 幾個解析規則背後的理由

**`"line"` 模式下 `Step` 這個字是必要的。** 沒有它，case 底下的任何說明文字、任何以數字開頭的行都會變成步驟。

**沒有 `Step` 關鍵字時，數字後面必須有分隔符號**（`3. Title`）。允許純空格的話，「2024 annual check」這種標題會被解析成第 2024 步。

**步驟一律以出現位置編號。** 標題裡寫的數字只被記錄下來，不會改變順序；不符時發出 `step.index_mismatch` 警告。默默重新編號會讓產生的函式名稱在計畫錯字時整批改變。

**`CASE_SECTION` 存在的理由**：真實的計畫文件在 `## Test Case List` 之前還有 Purpose、Environment 等章節，而且它們底下也有同層級的標題。不限定區段的話那些會被當成空的 test case。

### diagnostics 而不是例外

計畫是人手寫的，一定會髒。**可恢復的問題會收集起來隨結果一起回傳，而不是拋例外**，所以一次執行能報出輸入裡的所有問題，不是修一個發現一個。

三個嚴重度有明確後果：

| severity | 意義 |
|---|---|
| `error` | 產不出東西，拒絕生成 |
| `warning` | 有產出，但可能不是作者想要的 |
| `info` | 純提示 |

**`code` 是穩定識別碼，`message` 不是。** 客戶端和測試請依據 `code` 判斷；訊息文字隨時可能改寫。

---

## 7. 已知限制

分成三類：**刻意的取捨**（不要「修」它）、**目前的缺口**（可以補）、**尚未決定**。

### 7.1 刻意的取捨

**不保存任何產生結果。** 沒有歷史、沒有「上次產生的檔案」。要原地更新就得把現有檔案送回來。這是 3.4 的直接後果。

**不驗證產生的程式碼能否編譯。** TestForge 產生文字，不呼叫編譯器。目前靠人工或 CI 驗證。

**不處理權限與認證。** web 介面和 API 都沒有任何驗證，預設是內網或本機使用。對外開放前必須自己加一層。

**device 模組不隔離。** 如上所述，它是專案程式碼。不要讓不受信任的來源提供 device 資料夾。

**前端零依賴。** 沒有 npm、沒有建置流程、沒有 CDN。語法高亮是自己寫的約 30 行。理由是**裝置測試常在隔離網路上進行**，引用 CDN 會讓工具在沒有外網時直接壞掉。如果將來要引入前端框架，請先確認離線情境。

### 7.2 目前的缺口

**產生的程式碼沒有任何斷言——未實作的測試是綠的。**

這是目前**最需要注意**的一點。`simple_cpp` 產生的步驟只有註解和 `// TODO`，編譯執行後 exit code 是 **0**。也就是說一份完全沒實作的測試會「通過」。

原因是使用者提供的範本（`#include <iostream>` + `int main`）裡沒有任何斷言機制，而我們不應該自己發明一個。**要修很容易**：在 `devices/simple_cpp/device.py` 的 `_case_function()` 裡，為每個步驟產生一行會失敗的斷言（例如 `return 1;` 或你們自家的 assert 巨集）。

一般來說「還沒寫的測試應該是紅的」——綠的未實作測試比沒有測試更危險，因為有人會以為它通過了。

**web 介面沒有「只產生某一個 case」的選項。** CLI 的 `--case` 和 API 的 `options.case_selector` 都支援，但改成三步驟流程時我把下拉選單拿掉了，表單欄位還在但永遠是空的。要恢復的話是在 step 1 加一個選單並接回 `currentForm()`。

**切換步驟不會改變網址。** 瀏覽器的「上一頁」會離開整個頁面而不是回到前一步；重新整理會回到 step 1。要改善的話可以加 hash 路由（`#step-2`）。

**CJK 標題產生不出有意義的函式名稱。** C++ 識別碼實務上只能用 ASCII，所以「初始化裝置」這類標題會退回位置命名（`TestStep_01_Step1`）並發出 `naming.title_not_representable` 警告。重音拉丁字母會被折疊（`Prüfung` → `Prufung`），但 CJK 沒有對應的 ASCII 形式。目前只能在計畫裡用英文步驟標題，或在 `device.py` 裡自己接一個對照表。

**`Expected:` 有支援但目前的格式沒用到。** 解析器會把 `**Expected:**`、`Expected result:`、`預期結果：` 抽成 `step.expected`，但 `simple_cpp` 只把它寫成註解。如果將來要產生真的斷言，資料已經在那裡了。

**case 表格需要可辨識的名稱欄。** 欄名必須是 `Test Name`、`Name`、`Case`、`Test Case`、`測試名稱`、`名稱`、`案例` 其中之一。都不是的話會發 `case_table.no_name_column` 警告並且不附加任何 metadata——刻意不去猜哪一欄是名稱。

**只有一個 device，golden 測試也只蓋這一個。** `build(case)`（每 case 一組檔案）那條路徑目前只有臨時建構的測試 device 在覆蓋，沒有真實範例。

**OpenSpec 的 change 還沒 archive。** 規格還在 `openspec/changes/formalize-generation-pipeline/`，尚未升級到 `openspec/specs/`。裡面的 `tasks.md` 有一份尚未完成的稽核清單。

### 7.3 尚未決定

這些當初刻意留著，等真實使用情境出現再決定：

- **`main()` 裡的註解寫 `// Step1`、`// Step2`**，但那其實編號的是 test case 不是 step。照使用者給的範例做的，可能該改成 case 名稱。
- **每個 case 函式結尾補了 `return 0;`**。範例沒寫，但函式宣告為 `int` 而不 return 在 `-Werror` 下會被擋。
- **輸出檔名固定 `test_main.cpp`**。多份計畫產生到同一個目錄會互相覆蓋。
- **步驟正文被原樣寫成註解**。正文很長時產生的檔案會很冗。
- **diagnostic code 沒有棄用政策**。等到有外部客戶端依賴它們時再說。

---

## 8. 擴充時的注意事項

**加新的解析能力**：加進 `ParseOptions` 並預設關閉，讓 device 選擇啟用。不要改變既有 device 的預設行為。

**改 `device_api.py`**：那是 device 作者 import 的公開介面，改它等於 breaking change。

**改產生的程式碼外觀**：改完跑 `UPDATE_GOLDEN=1 pytest tests/test_golden.py`，然後**逐行看 diff**。golden 檔案的變更就是使用者會看到的變更。

**加 API 欄位**：同時改 `api/schemas/` 和 `api/mappers.py`。OpenAPI 的範例會被測試實際送出去驗證，所以別讓它們過期。

**改前端**：改完請在瀏覽器實際操作一遍，並且**量實際的 computed style 而不是只看截圖**。曾經發生過整組按鈕樣式被誤刪、截圖上看起來「有點怪但還好」、實際量到背景是瀏覽器預設灰的情況。

---

## 9. 詞彙

| 詞 | 意思 |
|---|---|
| **IR** | 解析後的中介表示：`TestCase` / `TestStep`。所有後續階段的共同輸入 |
| **anchor** | 一對 BEGIN/END 標記，中間的內容由 TestForge 管理 |
| **fragment** | 要放進某個 anchor 的程式碼字串，由 `device.py` 產生 |
| **artifact** | 一次產生的輸出檔案（路徑 + 內容 + created/updated） |
| **diagnostic** | 結構化的問題回報，有 severity 和穩定的 code |
| **device** | 一個產生目標：一個資料夾，含 `device.py` 與它的範本 |
