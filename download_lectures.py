import requests
import json
import os
import youtube_dl
import subprocess
import shutil

from ffprobe import FFProbe

PANOPTO_BASE = ""

MODULES = {}

"""
Place the value of your .ASPXAUTH token in the following variable or in ./.ASPXAUTH_token
"""
TOKEN = ""
if TOKEN == "" and os.path.isfile(".ASPXAUTH_token"):
    with open(".ASPXAUTH_token") as f:
        TOKEN = f.readline().rstrip()

s = requests.session() # cheeky global variable
s.cookies = requests.utils.cookiejar_from_dict({".ASPXAUTH": TOKEN})

def shorten_video(src, dst, retrying=False):
    if not os.path.isfile(dst):   
        print("Shortening " + src + "...")     
        subprocess.run(["auto-editor", src, "-o", dst, "--no_open"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        compress_video(dst)
    else:
        return # return if already made

    # check if no file was made by auto-editor
    if not os.path.isfile(dst) and not retrying:
        print("auto-editor failed to shorten video, retrying with transcode...")
        os.system("ffmpeg -i '" + src + "' -vf scale=1920:1080,fps=fps=30 '" + src + "_temp.mp4' -loglevel panic")
        if os.path.isfile(src + "_temp.mp4"):
            os.remove(src + "_temp.mp4")
            shutil.move(src + "_temp.mp4", src)

            shorten_video(src, dst, True)

    # notify user of new video
    #if os.path.isfile(dst):
    #    os.system("notify-send 'Lecture Downloader' 'New video downloaded at " + dst + "'")

def compress_video(src):
    if os.path.isfile(src):
        print("Compressing " + src + " with x265 crf 28...")
        subprocess.run(["ffmpeg", "-i", src, "-vcodec", "libx265", "-crf", "28", src + "_temp.mp4", "-loglevel", "panic"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.isfile(src + "_temp.mp4"):
            os.remove(src)
            shutil.move(src + "_temp.mp4", src)

def transcode_video(src, dimentions="1920:1080", fps="30"):
    os.system("ffmpeg -i '" + src + "' -vf scale=" + dimentions + ",fps=fps=" + fps + " -a:b 48k '" + src + "_temp.mp4' -loglevel panic")
    if os.path.isfile(src + "_temp.mp4"):
        os.remove(src + "_temp.mp4")
        shutil.move(src + "_temp.mp4", src)

def process_audio(src):
    print("Removing background noise from " + src + "...")
    os.system("ffmpeg -i '" + src + "' -af afftdn audio.wav -loglevel panic")
    if not os.path.isfile("audio.wav"):
        return

    print("Normalising audio for " + src + "...")
    subprocess.run(["ffmpeg-normalize", "audio.wav", "-o", "audio2.wav", "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Stitching video and audio back together for " + src + "...")
    if os.path.isfile("audio.wav"):
        os.remove("audio.wav")
    if os.path.isfile("audio2.wav"):
        os.system("ffmpeg -i '" + src + "' -i audio2.wav -map 0:0 -map 1:0 -c:v copy -c:a aac -b:a 256k -shortest OUTPUT.mp4 -loglevel panic")
        os.remove("audio2.wav")
        if os.path.isfile(src):
            os.remove(src)
        if os.path.isfile("OUTPUT.mp4"):
            shutil.move("OUTPUT.mp4", src)


# WHYYYY does panopto use at least 3 different types of API!?!?!?
def json_api(endpoint, params=dict(), post=False, paramtype="params"):
        if post:
                r = s.post(PANOPTO_BASE + endpoint, **{paramtype: params})
        else:
                r = s.get(PANOPTO_BASE + endpoint, **{paramtype: params})
        if not r.ok:
                print(r.text)
        return json.loads(r.text)


def name_normalize(name):
        return name.replace("/", "").replace(" ", "").replace(":","")#.replace("-","")


def dl_session(session):
        dest_dir = os.path.join(
                "downloads",
                MODULES[name_normalize(session["FolderName"])]#,
                #name_normalize(session["SessionName"])
        )
        if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
       
        edit_dir = os.path.join(
                "short",
                MODULES[name_normalize(session["FolderName"])]#,
                #name_normalize(session["SessionName"])
        )
        if not os.path.exists(edit_dir):
                os.makedirs(edit_dir)

        delivery_info = json_api("/Panopto/Pages/Viewer/DeliveryInfo.aspx", {
                "deliveryId": session["DeliveryID"],
                "responseType": "json"
        }, True, "data")
        
        streams = delivery_info["Delivery"]["Streams"]

        filename = name_normalize(session["SessionName"])
        
        for i in range(len(streams)):
                stream_index = ""
                if len(streams) > 1:
                    stream_index = "_" + str(i)

                dest_filename = os.path.join(dest_dir, filename + stream_index + ".mp4")
                if not os.path.isfile(dest_filename):
                    if len(streams) > 1:
                        print(filename + " contains " + str(len(streams)) + " streams, downloading part " + str(i+1) + "...")
                    else:
                        print("Downloading:" + dest_filename)
                    ydl_opts = {
                        "outtmpl": dest_filename,
                        "quiet": True
                    }
                    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([streams[i]["StreamUrl"]])

                    process_audio(dest_filename)

        if len(streams) == 2:
            if not os.path.isfile(os.path.join(dest_dir, filename + ".mp4")):
                meta_one=FFProbe(os.path.join(dest_dir, filename + "_0" + ".mp4"))
                meta_two=FFProbe(os.path.join(dest_dir, filename + "_1" + ".mp4"))
                one_has_video=False
                two_has_video=False

                for stream in meta_one.streams:
                    if stream.is_video():
                        one_has_video=True
                for stream in meta_two.streams:
                    if stream.is_video():
                        two_has_video=True

                if one_has_video and two_has_video:
                    print("Scaling video streams...")
                    #transcode_video(os.path.join(dest_dir, filename + "_0" + ".mp4"), "960:540")
                    #transcode_video(os.path.join(dest_dir, filename + "_1" + ".mp4"), "960:540")

                    print("Merging video streams...")
                    str_cmd = 'ffmpeg -y -i "__STREAM_ONE" -i "__STREAM_TWO" -filter_complex "nullsrc=size=1920x540 [base]; [0:v] scale=960x540 [upperleft]; [1:v] setpts=PTS-STARTPTS, scale=960x540 [upperright]; [base][upperleft] overlay=shortest=1 [tmp1]; [tmp1][upperright] overlay=shortest=1:x=960" -c:v libx264 "__OUTPUT_STREAM" -loglevel panic'
                    str_cmd = str_cmd.replace("__STREAM_ONE", os.path.join(dest_dir, filename + "_0" + ".mp4"))
                    str_cmd = str_cmd.replace("__STREAM_TWO", os.path.join(dest_dir, filename + "_1" + ".mp4"))
                    str_cmd = str_cmd.replace("__OUTPUT_STREAM", os.path.join(dest_dir, filename + ".mp4"))
                    os.system(str_cmd)
                elif one_has_video:
                    print("Merging video streams...")
                    str_cmd = 'ffmpeg -y -i "__STREAM_ONE" -i "__STREAM_TWO" -map 0:0 -map 1:0 -c:v copy -c:a aac -b:a 256k -shortest "__OUTPUT_STREAM" -loglevel panic'
                    str_cmd = str_cmd.replace("__STREAM_ONE", os.path.join(dest_dir, filename + "_0" + ".mp4"))
                    str_cmd = str_cmd.replace("__STREAM_TWO", os.path.join(dest_dir, filename + "_1" + ".mp4"))
                    str_cmd = str_cmd.replace("__OUTPUT_STREAM", os.path.join(dest_dir, filename + ".mp4"))
                    os.system(str_cmd)
                elif two_has_video:
                    print("Merging video streams...")
                    str_cmd = 'ffmpeg -y -i "__STREAM_ONE" -i "__STREAM_TWO" -map 0:0 -map 1:0 -c:v copy -c:a aac -b:a 256k -shortest "__OUTPUT_STREAM" -loglevel panic'
                    str_cmd = str_cmd.replace("__STREAM_TWO", os.path.join(dest_dir, filename + "_0" + ".mp4"))
                    str_cmd = str_cmd.replace("__STREAM_ONE", os.path.join(dest_dir, filename + "_1" + ".mp4"))
                    str_cmd = str_cmd.replace("__OUTPUT_STREAM", os.path.join(dest_dir, filename + ".mp4"))
                    os.system(str_cmd)

        elif len(streams) > 2:
            print("number of streams is not supported")
            return

        shorten_video(os.path.join(dest_dir, filename + ".mp4"), os.path.join(edit_dir, filename + ".mp4"))

                
def dl_folder(folder):
        sessions = json_api("/Panopto/Services/Data.svc/GetSessions", {
                "queryParameters": {
                        "folderID": folder["Id"],
                }
        }, True, "json")["d"]["Results"]

        for session in sessions:
                dl_session(session)


folders = json_api("/Panopto/Api/v1.0-beta/Folders", {
        "parentId": "null",
        "folderSet": 1
})

#if os.path.isfile("/home/will/Documents/lectures/lock"):
#    print("Script is already running!\n(delete the lock file if the script is not running")

#else:
#    open("/home/will/Documents/lectures/lock","a").close()

for folder in folders:
        """
                Put an if statement here based on folder["Name"] if you just want a certain
                module or year etc.
                e.g.:
        """
        for m in MODULES.keys():
                if folder["Name"].startswith(m):
                        dl_folder(folder)

#    os.remove("/home/will/Documents/lectures/lock")
