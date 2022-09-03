import sys
from math import ceil
from itertools import chain
import requests
from time import sleep
import json

token, guild, channel, user, refpoint = sys.argv[1:]

msgs = set()

headers = {
        "authorization": token,
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) QtWebEngine/5.15.4 Chrome/87.0.4280.144 Safari/537.36",
        "referer": f"https://discord.com/channels/{guild}/{channel}"
}

def messages(guild, user, refpoint):
    params = {"author_id": user, "max_id": refpoint}
    searchurl = f"https://discord.com/api/v9/guilds/{guild}/messages/search"
    r = requests.get(searchurl, headers=headers, params=params).json()
    msgs = r["total_results"]
    print(msgs)
    for [n] in r["messages"]: yield n
    params["offset"] = len(r["messages"])
    roffset = len(r["messages"])
    while roffset <= msgs:
        print(f"{roffset=}")
        if params["offset"] >= 5000:
            params["max_id"] = str(int(r["messages"][-1][0]["id"]) - 1)
            del params["offset"]
        r = requests.get(searchurl, headers=headers, params=params).json()
        if not "messages" in r:
            time = 5*r["retry_after"]
            print(f"Sleeping for {time} seconds")
            sleep(time)
            r = requests.get(searchurl, headers=headers, params=params).json()
        for [n] in r["messages"]: yield n
        params["offset"] = (params["offset"] if "offset" in params else 0) + len(r["messages"])
        roffset += len(r["messages"])
        sleep(0.1)




def download_context(guild, user, refpoint):
    for message in messages(guild, user, refpoint):
        if message["id"] in msgs: continue
        chid = message["channel_id"]
        msgid = message["id"]
        url = f"https://discord.com/api/v9/channels/{chid}/messages?before={msgid}&limit=100"
        context = requests.get(url, headers=headers).json()
        for idx, submsg in enumerate(context[:80]):
            if submsg["author"]["id"] != user: continue
            msgs.add(submsg["id"])
            yield [submsg, *context[idx+1:idx+1+20]]
        yield [message, *context[:20]]
        sleep(0.1)

if __name__ == "__main__": 
    counter = 1
    with open("messages.json", "w") as f:
        gen = download_context(guild, user, refpoint)
        for context in gen:
            print(counter)
            f.write(",")
            json.dump(context, f)
            counter += 1

