"""飞书多维表格 API 封装"""
from __future__ import annotations

import re
from typing import Any

import requests

BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        resp = requests.post(
            f"{BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取飞书 token 失败: {data}")
        self._token = data["tenant_access_token"]
        return self._token

    def _get(self, path: str, params: dict | None = None) -> dict:
        token = self._get_token()
        resp = requests.get(
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书 API error [{path}]: {data.get('msg', data)}")
        return data

    def _post(self, path: str, body: dict) -> dict:
        token = self._get_token()
        resp = requests.post(
            f"{BASE_URL}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书 API error [{path}]: {data.get('msg', data)}")
        return data

    # ---- Bitable ----

    def list_spreadsheets(self, page_token: str | None = None) -> tuple[list[dict], str | None]:
        params: dict[str, Any] = {"page_size": 100, "type": "bitable"}
        if page_token:
            params["page_token"] = page_token
        data = self._get("/drive/v1/files", params)
        items: list[dict] = []
        for f in data.get("data", {}).get("files", []):
            items.append({"name": f["name"], "token": f["token"]})
        next_token = data.get("data", {}).get("page_token")
        return items, next_token

    def list_tables(self, app_token: str) -> list[dict]:
        data = self._get(f"/bitable/v1/apps/{app_token}/tables", {"page_size": 100})
        tables: list[dict] = []
        for item in data.get("data", {}).get("items", []):
            tables.append({"name": item["name"], "id": item["table_id"]})
        return tables

    def list_fields(self, app_token: str, table_id: str) -> list[dict]:
        data = self._get(
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            {"page_size": 100},
        )
        fields: list[dict] = []
        for item in data.get("data", {}).get("items", []):
            fields.append({
                "name": item["field_name"],
                "id": item["field_id"],
                "type": item["type"],
            })
        return fields

    # ---- Records ----

    def list_records(self, app_token: str, table_id: str, *, page_size: int = 500) -> list[dict]:
        """分页拉取多维表格全部记录，返回 fields 列表"""
        all_records: list[dict] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": min(page_size, 500)}
            if page_token:
                params["page_token"] = page_token
            data = self._get(
                f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                params,
            )
            for item in data.get("data", {}).get("items", []):
                all_records.append(item.get("fields", {}))
            if not data.get("data", {}).get("has_more"):
                break
            page_token = data.get("data", {}).get("page_token")
            if not page_token:
                break
        return all_records



    def batch_create_records(
        self, app_token: str, table_id: str,
        records: list[dict], field_types: dict | None = None,
    ) -> int:
        total = 0
        batch_size = 500
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            record_list: list[dict] = []
            for record in batch:
                fields: dict[str, Any] = {}
                for key, value in record.items():
                    formatted = self._format_field(key, value, field_types)
                    if formatted != "":
                        fields[key] = formatted
                record_list.append({"fields": fields})
            body = {"records": record_list}
            self._post(
                f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                body,
            )
            total += len(batch)
        return total

    def _format_field(self, field_id: str, value: Any, field_types: dict | None = None) -> Any:
        if value is None or value == "" or value == "nan":
            return ""
        ft = (field_types or {}).get(field_id, 1)
        if ft == 15:
            url = str(value).strip()
            if url and not url.startswith("http"):
                url = "https://" + url
            return {"link": url, "text": url}
        return str(value)


def parse_app_token(text: str) -> str | None:
    """从飞书多维表格 URL 中提取 app_token"""
    text = text.strip()
    if not text:
        return None
    if "/" not in text and "." not in text:
        return text
    m = re.search(r'/base/([A-Za-z0-9]+)', text)
    return m.group(1) if m else None
