# AI digital frame

## start
1. install requirements. Note: when you install torch, make sure you install correct cuda version.
2. go to `config.json` to set `openai` => `api_key`
3. make sure you have start [AUTOMATIC1111/stable-diffusion-webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui) and has start flag `--api`
4. start server
```commandline
python app.py [--logging-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET,critical,fatal,error,warn,warning,info,debug,notset}] [--env] [-h]
```

## code
* `app.py`: 程式碼進入點
* `util.py`: 輔助函數
* `test.py`: 用來測試用的code
* `config.json`: 設定檔

## api doc
You can start the server and go to http://127.0.0.1:5000 to read the doc