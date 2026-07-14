# 外部 API 接口规范

在网站中填入录播/集控平台 **根地址**（如 `http://10.x.x.x/api`），系统会自动尝试以下路径。

## 教室列表

```
GET {api_url}/rooms
GET {api_url}/api/rooms
GET {api_url}/classrooms
```

响应示例：

```json
{
  "rooms": [
    {
      "id": "py-nh-101",
      "building": "南海楼",
      "room": "NH101",
      "name": "南海楼 · NH101",
      "status": "in_use",
      "devices": "PC,投影,录播",
      "stream_url": "http://内网/optional/direct/preview.jpg"
    }
  ]
}
```

`status` 支持：`in_use` / `idle` / `offline` / `fault`（或 `online` / `using` / `error`）

## 实时画面

```
GET {api_url}/rooms/{id}/snapshot.jpg   # 单帧 JPEG
GET {api_url}/rooms/{id}/mjpeg          # MJPEG 流（推荐）
```

可选请求头：`Authorization: Bearer <api_key>` 或 `X-Api-Key: <key>`

## 本地测试

不填内网地址时，可用内置模拟 API：

```
http://127.0.0.1:8080/api/mock-platform
```

登录页点击蓝色示例地址可自动填入。
