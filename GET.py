import json
import os
import git
from datetime import datetime
from shutil import copy2
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# JSON生成部分 (以前のコードと同様)
def initWebDriver():
    driver_path = "C:/python/tdr_guide/resource/chromedriver.exe"

    # オプション設定
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Serviceオブジェクトを作成
    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=options)

    return driver


def WaitElement(driver, CSS_SELECTOR):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, CSS_SELECTOR))
        )
    except:
        print("Timeout: Element not found")
        return False


def getTDRData(driver, url, date_str):
    print("getTDRData")
    driver.get(url)
    WaitElement(driver, f"div.date-{date_str}")

    areas = driver.find_elements(By.CSS_SELECTOR, "p.area")
    names = driver.find_elements(By.CSS_SELECTOR, "h3.heading3:not(.linkText)")
    tagAreas = driver.find_elements(By.CSS_SELECTOR, "div.tagArea")
    realtimeInformation = driver.find_elements(By.CSS_SELECTOR, f"div.date-{date_str}")

    # 出力ファイル名決定
    os.makedirs(f"C:/python/tdr_guide/output/{date_str}", exist_ok=True)
    park_code = "tds" if "tds" in url else "tdl"
    json_path = f"C:/python/tdr_guide/output/{date_str}/{park_code}.json"

    # JSONファイル読み込みまたは新規作成
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as json_file:
            json_data = json.load(json_file)
    else:
        json_data = {}

    for (area, name, info, tagArea) in zip(areas, names, realtimeInformation, tagAreas):
        areaName = area.text.strip()
        nameText = name.text.strip().replace(" NEW", "")

        updateTime = info.find_elements(By.CSS_SELECTOR, "p.update")
        updateTime = updateTime[0].text.replace("運営/公演状況", "") if updateTime else ""

        waitTime = info.find_elements(By.CSS_SELECTOR, "span.time")
        waitTime = waitTime[0].text if waitTime else ""

        operationTime = info.find_elements(By.CSS_SELECTOR, "span.operationTime")
        operationTime = operationTime[0].text if operationTime else ""

        operation = info.find_elements(By.CSS_SELECTOR, "span.operation")
        operation = operation[0].text if operation else ""

        operationWarning = info.find_elements(By.CSS_SELECTOR, "span.operation.warning")
        operationWarning = operationWarning[0].text if operationWarning else ""

        is_cancel = info.find_elements(By.CSS_SELECTOR, "ul.is-cancel")
        is_cancel = is_cancel[0].text if is_cancel else None

        if is_cancel:
            operation = "運営・公演中止"

        # プライオリティ・アクセス・エントランス情報を取得
        tags = tagArea.text.strip()

        isDPA = False
        isPP = False
        isSP = False

        DPA_tag = "ディズニー・プレミアアクセス対象"
        PP_tag = "40周年記念プライオリティパス対象"
        SP_tag = "スタンバイパス対象"

        if DPA_tag in tags:
            isDPA = True
        if PP_tag in tags:
            isPP = True
        if SP_tag in tags:
            isSP = True

        # プライオリティ・アクセス・エントランスの在庫状況を取得
        DPA_stock = False
        PP_stock = False
        SP_stock = False

        DPA_isStockText = "ディズニー・プレミアアクセス販売中"
        PP_isStockText = "40周年記念プライオリティパス発行中"
        SP_isStockText = "スタンバイパス発行中"

        if isDPA and DPA_isStockText in operationWarning:
            DPA_stock = True
        elif isDPA:
            DPA_stock = False
        else:
            DPA_stock = None

        if isPP and PP_isStockText in operationWarning:
            PP_stock = True
        elif isPP:
            PP_stock = False
        else:
            PP_stock = None

        if isSP and SP_isStockText in operationWarning:
            SP_stock = True
        elif isPP:
            SP_stock = False
        else:
            SP_stock = None

        now_time = datetime.now().strftime("%H:%M")

        # 構造がなければ初期化
        if areaName not in json_data:
            json_data[areaName] = {}

        if nameText not in json_data[areaName]:
            json_data[areaName][nameText] = {
                "Realtime": {},
                "History": []
            }

        # Realtime を更新
        json_data[areaName][nameText]["Realtime"] = {
            "update_time": updateTime,
            "wait_time": waitTime,
            "operation": operation,
            "operation_time": operationTime,
            "operation_warning": operationWarning,
            "DPA": {
                "use": isDPA,
                "stock": DPA_stock
            },
            "PP": {
                "use": isPP,
                "stock": PP_stock
            },
            "SP": {
                "use": isSP,
                "stock": SP_stock
            },
        }

        if not is_cancel:
            # History に追記
            json_data[areaName][nameText]["History"].append({
                "time": now_time,
                "update_time": updateTime,
                "wait_time": waitTime,
                "operation": operation,
                "operation_time": operationTime,
                "operation_warning": operationWarning,
                "DPA": {
                    "use": isDPA,
                    "stock": DPA_stock
                },
                "PP": {
                    "use": isPP,
                    "stock": PP_stock
                },
                "SP": {
                    "use": isSP,
                    "stock": SP_stock
                },
            })

        print(f"エリア: {areaName} アトラクション: {nameText} → History追加: {now_time}")

    # 保存
    with open(f"C:/python/tdr_guide/output/{date_str}/{park_code}.json", "w", encoding="utf-8") as outfile:
        json.dump(json_data, outfile, indent=4, ensure_ascii=False)

    driver.quit()


# GitHubへのアップロード部分
def upload_to_github(date_str):
    # GitHubのリポジトリパス
    repo_path = "path/to/your/tdr-guide-json"
    json_files = ["tds.json", "tdl.json"]

    # Gitリポジトリの更新
    repo = git.Repo(repo_path)
    index = repo.index

    # 各JSONファイルをコピー
    for json_file in json_files:
        json_path = f"C:/python/tdr_guide/output/{date_str}/{json_file}"
        if os.path.exists(json_path):
            dest_path = os.path.join(repo_path, date_str, json_file)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            copy2(json_path, dest_path)

            # リポジトリに追加
            index.add([dest_path])

    # コミットしてプッシュ
    commit_message = f"Update {date_str} TDS/TDL data"
    index.commit(commit_message)
    origin = repo.remotes.origin
    origin.push()


def main():
    # 実行時間の制限（8:50〜21:00 の間だけ実行）
    now = datetime.now().time()
    start_time = datetime.strptime("08:50", "%H:%M").time()
    end_time = datetime.strptime("21:01", "%H:%M").time()

    if not (start_time <= now <= end_time):
        print(f"{now.strftime('%H:%M')} は対象時間外のためスキップします。")
        return

    date_str = datetime.now().strftime("%Y%m%d")

    URLs = [
        "https://www.tokyodisneyresort.jp/tds/attraction.html",
        "https://www.tokyodisneyresort.jp/tdl/attraction.html"
    ]

    # 取得したデータをJSONファイルとして保存
    driver = initWebDriver()
    for url in URLs:
        getTDRData(driver, url, date_str)

    # JSONファイルをGitHubにアップロード
    upload_to_github(date_str)

if __name__ == "__main__":
    main()
