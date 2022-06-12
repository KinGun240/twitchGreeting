# Copyright 2022 KinGun
# This software is released under the MIT License, see LICENSE.

from twitchio.ext import commands
from playsound import playsound

from shutil import rmtree
import os
import glob
import csv
import importlib
import pandas as pd
import sys
import signal
import unicodedata

Debug = True

# バージョン
ver = '1.1.0'
userExpFile = "userExpList.csv"

# 各種初期設定 #####################################
# bot用コンフィグの読み込み
try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '.'))
    configGreeting = importlib.import_module('config')
    # configGreeting.Twitch_Channel = configGreeting.Twitch_Channel.lower()
    # configGreeting.Trans_Username = configGreeting.Trans_Username.lower()
    print("Read config.py")
    # remove "#" mark ------
    if configGreeting.Twitch_Channel.startswith('#'):
        print("Find # mark at channel name! I remove '#' from 'config:Twitch_Channel'")
        configGreeting.Twitch_Channel = configGreeting.Twitch_Channel[1:]
    # remove "oauth:" mark ------
    if configGreeting.Trans_OAUTH.startswith('oauth:'):
        print("Find 'oauth:' at OAUTH text! I remove 'oauth:' from 'config:Trans_OAUTH'")
        configGreeting.Trans_OAUTH = configGreeting.Trans_OAUTH[6:]
except Exception as e:
    print(e)
    print('Please make [config.py] and put it with twitchTransFN')
    input()  # stop for error!!


# botの初期化
try:
    bot = commands.Bot(
        irc_token="oauth:" + configGreeting.Trans_OAUTH,
        client_id=configGreeting.CLIENT_ID,
        nick=configGreeting.Trans_Username,
        prefix=configGreeting.BOT_PREFIX,
        initial_channels=[configGreeting.Twitch_Channel]
    )
except Exception as e:
    print(e)
    print('Please check [config.py]')
    input()  # stop for error!!


# GreetingBot用パラメーターの読み込み
try:
    obsCommands = importlib.import_module('param_greetingBot')
    print("Read param_greetingBot.py")
except Exception as e:
    print(e)
    print('Please make [param_greetingBot.py] and put it with Greetingbot')
    input()  # stop for error!!


# 内部変数の設定 ----------
# ユーザー経験値リストの読み込み
try:
    # with open(f"data/{userExpFile}", "r", encoding="utf8",  newline="") as f:
    #     csvReader = csv.DictReader(f, skipinitialspace=True)
    #     UserExpList = [row for row in csvReader]
    #     print(f"Read {userExpFile}")
    UserExpList = pd.read_csv(f"data/{userExpFile}")
    print(f"Read {userExpFile}")
except Exception as e:
    print(e)
    print(f'Please check [{userExpFile}] and put it with Greetingbot')
    input()
if Debug:
    print(UserExpList)

# 初見ユーザーリストの初期化
FirstUserList = ['']
# FirstUserList = [str.lower() for str in FirstUserList]


# bot処理 #####################################
# bot起動時処理
@bot.event
async def event_ready():
    print(f"{configGreeting.Trans_Username}がオンラインになりました!")
    ws = bot._ws  # this is only needed to send messages within event_ready
    await ws.send_privmsg(configGreeting.Twitch_Channel, f"/color {configGreeting.TextColor}")
    await ws.send_privmsg(configGreeting.Twitch_Channel, f"/me has landed! Hello!!")

    # 書き込み開始のファイル出力
    if configGreeting.IsSaveCommentsFile:
        with open('comments.csv', 'a') as commentsFile:
            writer = csv.writer(commentsFile)
            writer.writerow(['#Start Write Comments'])
            commentsFile.close()


# メッセージ受信時処理 ----------
@bot.event
async def event_message(ctx):
    msg = ctx.content
    time = pd.Timestamp(ctx.timestamp, unit='s', tz='UTC')
    time = time.tz_convert('Asia/Tokyo')
    user = ctx.author.name.lower()
    name = ctx.author.display_name
    isMod = ctx.author.is_mod
    is_Sub = ctx.author.is_subscriber
    if len(ctx.author.badges) > 0:
        badges = ctx.author.badges['broadcaster']
    else:
        badges = None

    if Debug:
        print(f'echo: {ctx.echo}, {ctx.content}')
    # メッセージがコマンドの場合は抜ける
    # await bot.handle_commands(ctx)
    if ctx.content.startswith('!'):
        return
    # メッセージがbotまたはストリーマーの投稿の場合は抜ける
    if not Debug:
        if ctx.echo or user == bot.nick or badges == '1':
            return

    # コメント用の効果音を鳴らす
    try:
        if configGreeting.IsPlaySoundComment:
            playsound('./sound/{}'.format(configGreeting.CommentSound), True)
    except Exception as e:
        print('sound error: [!sound] command can not play sound...')
        if Debug:
            print(e.args)

    # タイムスタンプ、ユーザー、コメントのファイル出力
    try:
        if configGreeting.IsSaveCommentsFile:
            with open('comments.csv', 'a') as commentsFile:
                writer = csv.writer(commentsFile)
                writer.writerow([time, user, msg])
                commentsFile.close()
    except Exception as e:
        print('file error: [comments.csv] can not save...')
        if Debug:
            print(e.args)

    # レベルアップ処理 ----------
    global UserExpList
    key = 'UserName'
    value = 'MessageCount'
    # ユーザーがユーザー経験値リストに存在する場合は経験値を１追加
    # 存在しない場合はユーザー経験値リストに追加
    try:
        row = UserExpList.query(f"{key} in ['{user}']")
        if not row.empty:
            UserExpList.loc[UserExpList[key] == user, value] = row[value] + 1
        else:
            newRow = pd.DataFrame([[user, 1]], columns=[key, value])
            print(newRow)
            UserExpList = UserExpList.append(newRow, ignore_index=True)
        print(UserExpList)
    except Exception as e:
        print('error: UserExpList not read...')
        if Debug:
            print(e.args)

    # ユーザー経験値リストを保存しなおす
    try:
        UserExpList.to_csv(f"data/{userExpFile}", index=False)
    except Exception as e:
        print(f'file error: [{userExpFile}] can not save...')
        if Debug:
            print(e.args)

    # 経験値に応じてレベルアップさせる

    # 挨拶処理 ----------
    global FirstUserList
    # ユーザーが初見ユーザーリストに存在する場合は処理終了
    # いない場合は初見ユーザーリストへ追加
    print('USER:{}'.format(user))
    if user in FirstUserList:
        return
    FirstUserList.append(user)

    # チャット欄へ初見コメント出力
    if configGreeting.IsGreetingComment:
        strLen = len(msg)
        multiLen = count_text(msg)

        if strLen != multiLen or ctx.content.startswith('!'):
            out_text = 'ようこそ、{} さん！'.format(name)
        else:
            out_text = 'Hello, {} !!'.format(name)
        await ctx.send("/me " + out_text)

    # 初見挨拶用の効果音を鳴らす
    try:
        if configGreeting.IsPlaySoundGreeting:
            playsound('./sound/{}'.format(configGreeting.GreetingSound), True)
            # playsound('./sound/tm2_chime002.wav', True)
    except Exception as e:
        print('sound error: [!sound] command can not play sound...')
        if Debug:
            print(e.args)

    # コンソールへの表示
    print(out_text)


# ハローコマンド時処理 ----------
@bot.command(name='hello')
async def hello(ctx):
    await ctx.send(f'{ctx.author.name}さん こんにちは～ KonCha')


#####################################
# マルチバイト文字を判別して文字列の長さを返す処理 -------------
def count_text(message):
    # 文字列長カウント用の変数を定義
    text_length = 0
    # 文章中の文字数分ループを回す
    for i in message:
        letter = unicodedata.east_asian_width(i)
        print(letter)
        if letter == 'H':       # 半角
            text_length = text_length + 1
        elif letter == 'Na':    # 半角
            text_length = text_length + 1
        elif letter == 'F':     # 全角
            text_length = text_length + 2
        elif letter == 'A':     # 全角
            text_length = text_length + 2
        elif letter == 'W':     # 全角
            text_length = text_length + 2
        else:                   # 半角
            text_length = text_length + 1
    return text_length


#####################################
# 最後のクリーンアップ処理 -------------
def cleanup():
    print("!!!Clean up!!!")

    # Cleanup処理いろいろ

    # time.sleep(1)
    print("!!!Clean up Done!!!")


#####################################
# sig handler  -------------
def sig_handler(signum, frame) -> None:
    sys.exit(1)


#####################################
# _MEI cleaner  -------------
# Thanks to Sadra Heydari
# @ https://stackoverflow.com/questions/57261199/python-handling-the-meipass-folder-in-temporary-folder
def CLEANMEIFOLDERS():
    try:
        base_path = sys._MEIPASS

    except Exception:
        base_path = os.path.abspath(".")

    if Debug:
        print(f'_MEI base path: {base_path}')
    base_path = base_path.split("\\")
    base_path.pop(-1)
    temp_path = ""
    for item in base_path:
        temp_path = temp_path + item + "\\"

    mei_folders = [f for f in glob.glob(temp_path + "**/", recursive=False)]
    for item in mei_folders:
        if item.find('_MEI') != -1 and item != sys._MEIPASS + "\\":
            rmtree(item)


# メイン処理 ###########################
def main():
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        # 以前に生成された _MEI フォルダを削除する
        CLEANMEIFOLDERS()

        # bot
        bot.run()

    except Exception as e:
        if Debug:
            print(e)
        input()  # stop for error!!

    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        cleanup()
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)


if __name__ == "__main__":
    sys.exit(main())
