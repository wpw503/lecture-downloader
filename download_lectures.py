import requests
import json
import os
import youtube_dl
import subprocess
import shutil

from ffprobe import FFProbe

s = requests.session()


def main():
    panopto_base_url = ""  # base part of the panopto url
    aspxauth_token = ""  # ASPXAUTH string from the .ASPXAUTH cookie
    folders = dict()  # all folders that are to be downloaded, with aliases

    panopto_base_url, folders, aspxauth_token = load_settings()

    s.cookies = requests.utils.cookiejar_from_dict(
        {".ASPXAUTH": aspxauth_token})

    download_videos(panopto_base_url, folders)


def load_settings():
    settings_file_path = "settings.json"
    data = ""

    if os.path.isfile("alt_settings.json"):
        settings_file_path = "alt_settings.json"

    if not os.path.isfile(settings_file_path):
        with open(settings_file_path, "w") as f:
            f.write(
                '{"base_url": "","modules": [{"example":"mapping"}],".ASPXAUTH": ""}')

    with open(settings_file_path) as f:
        data = f.read().rstrip()

    jdata = json.loads(data)

    return jdata["base_url"], jdata["modules"][0], jdata[".ASPXAUTH"]


def download_videos(base_url, folders):
    all_folders = json_api("/Panopto/Api/v1.0-beta/Folders", base_url, {
        "parentId": "null",
        "folderSet": 1
    })

    for folder in all_folders:
        for m in folders.keys():
            if folder["Name"].startswith(m):
                download_folder(base_url, folders, folder)


def json_api(endpoint, base_url, params=dict(), post=False, paramtype="params"):
    if post:
        r = s.post(base_url + endpoint, **{paramtype: params})
    else:
        r = s.get(base_url + endpoint, **{paramtype: params})
    if not r.ok:
        print(r.text)
    return json.loads(r.text)


def name_normalize(name):
    return name.replace("/", "").replace(" ", "").replace(":", "")


def download_folder(base_url, folders, folder):
    sessions = json_api("/Panopto/Services/Data.svc/GetSessions", base_url, {
        "queryParameters": {
            "folderID": folder["Id"],
        }
    }, True, "json")["d"]["Results"]

    for session in sessions:
        download_session(base_url, folders, session)


def download_session(base_url, folders, session):
    dest_dir = os.path.join(
        "downloads",
        folders[name_normalize(session["FolderName"])]
    )
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    delivery_info = json_api("/Panopto/Pages/Viewer/DeliveryInfo.aspx", base_url, {
        "deliveryId": session["DeliveryID"],
        "responseType": "json"
    }, True, "data")

    streams = delivery_info["Delivery"]["Streams"]

    filename = name_normalize(session["SessionName"])

    for i in range(len(streams)):
        stream_index = ""
        if len(streams) > 1:
            stream_index = "_" + str(i)

        dest_filename = os.path.join(
            dest_dir, filename + stream_index + ".mp4")
        if not os.path.isfile(dest_filename):
            if len(streams) > 1:
                print(filename + " contains " + str(len(streams)) +
                      " streams, downloading part " + str(i+1) + "...")
            else:
                print("Downloading:" + dest_filename)
            ydl_opts = {
                "outtmpl": dest_filename,
                "quiet": True
            }
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([streams[i]["StreamUrl"]])

    merge_streams(streams, dest_dir, filename)
    process_file(os.path.join(dest_dir, filename + ".mp4"), filename,
                 folders[name_normalize(session["FolderName"])])


def merge_streams(streams, dest_dir, filename):
    if len(streams) == 2:
        if not os.path.isfile(os.path.join(dest_dir, filename + ".mp4")):
            meta_one = FFProbe(os.path.join(
                dest_dir, filename + "_0" + ".mp4"))
            meta_two = FFProbe(os.path.join(
                dest_dir, filename + "_1" + ".mp4"))
            one_has_video = False
            two_has_video = False

            for stream in meta_one.streams:
                if stream.is_video():
                    one_has_video = True
            for stream in meta_two.streams:
                if stream.is_video():
                    two_has_video = True

            if one_has_video and two_has_video:
                print("Merging video streams...")
                str_cmd = 'ffmpeg -y -i "__STREAM_ONE" -i "__STREAM_TWO" -filter_complex "nullsrc=size=1920x540 [base]; [0:v] scale=960x540 [upperleft]; [1:v] setpts=PTS-STARTPTS, scale=960x540 [upperright]; [base][upperleft] overlay=shortest=1 [tmp1]; [tmp1][upperright] overlay=shortest=1:x=960" -c:v libx264 "__OUTPUT_STREAM" -loglevel panic'
                str_cmd = str_cmd.replace("__STREAM_ONE", os.path.join(
                    dest_dir, filename + "_0" + ".mp4"))
                str_cmd = str_cmd.replace("__STREAM_TWO", os.path.join(
                    dest_dir, filename + "_1" + ".mp4"))
                str_cmd = str_cmd.replace(
                    "__OUTPUT_STREAM", os.path.join(dest_dir, filename + ".mp4"))
                os.system(str_cmd)
            else:
                print("Merging video streams...")
                str_cmd = 'ffmpeg -y -i "__STREAM_ONE" -i "__STREAM_TWO" -map 0:0 -map 1:0 -c:v copy -c:a aac -b:a 256k -shortest "__OUTPUT_STREAM" -loglevel panic'

                if one_has_video and two_has_video:
                    str_cmd = 'ffmpeg -y -i "__STREAM_ONE" -i "__STREAM_TWO" -filter_complex "nullsrc=size=1920x540 [base]; [0:v] scale=960x540 [upperleft]; [1:v] setpts=PTS-STARTPTS, scale=960x540 [upperright]; [base][upperleft] overlay=shortest=1 [tmp1]; [tmp1][upperright] overlay=shortest=1:x=960" -c:v libx264 "__OUTPUT_STREAM" -loglevel panic'
                    str_cmd = str_cmd.replace("__STREAM_ONE", os.path.join(
                        dest_dir, filename + "_0" + ".mp4"))
                    str_cmd = str_cmd.replace("__STREAM_TWO", os.path.join(
                        dest_dir, filename + "_1" + ".mp4"))
                elif one_has_video:
                    str_cmd = str_cmd.replace("__STREAM_ONE", os.path.join(
                        dest_dir, filename + "_0" + ".mp4"))
                    str_cmd = str_cmd.replace("__STREAM_TWO", os.path.join(
                        dest_dir, filename + "_1" + ".mp4"))
                elif two_has_video:
                    str_cmd = str_cmd.replace("__STREAM_TWO", os.path.join(
                        dest_dir, filename + "_0" + ".mp4"))
                    str_cmd = str_cmd.replace("__STREAM_ONE", os.path.join(
                        dest_dir, filename + "_1" + ".mp4"))

                str_cmd = str_cmd.replace(
                    "__OUTPUT_STREAM", os.path.join(dest_dir, filename + ".mp4"))

                os.system(str_cmd)

    elif len(streams) > 2:
        print("number of streams is not supported")
        return


def process_file(src, filename, folder):
    short_dir = os.path.join(
        "short",
        folder
    )
    if not os.path.exists(short_dir):
        os.makedirs(short_dir)

    short_filename = os.path.join(short_dir, filename + ".mp4")

    if not os.path.isfile(short_filename):
        shutil.copy(src, short_filename)

        process_audio(short_filename)
        shorten_video(short_filename)
        compress_video(short_filename)


def process_audio(src):
    print("Removing background noise from " + src + "...")
    os.system("ffmpeg -i '" + src + "' -af afftdn '" +
              src + "_audio.wav" + "' -loglevel panic")
    if not os.path.isfile(src + "_audio.wav"):
        return

    print("Normalising audio for " + src + "...")
    subprocess.run(["ffmpeg-normalize", src + "_audio.wav", "-o", src + "_audio2.wav",
                    "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Stitching video and audio back together for " + src + "...")
    if os.path.isfile(src + "_audio.wav"):
        os.remove(src + "_audio.wav")
    if os.path.isfile(src + "_audio2.wav"):
        os.system("ffmpeg -i '" + src +
                  "' -i '" + src + "_audio2.wav" + "' -map 0:0 -map 1:0 -c:v copy -c:a aac -b:a 256k -shortest '" + src + "_temp.mp4" + "' -loglevel panic")
        os.remove(src + "_audio2.wav")

        if os.path.isfile(src + "_temp.mp4"):
            shutil.move(src + "_temp.mp4", src)


def shorten_video(src):
    print("Shortening " + src + "...")
    subprocess.run(["auto-editor", src, "-o", src + "_temp.mp4", "--no_open"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.isfile(src + "_temp.mp4"):
        shutil.move(src + "_temp.mp4", src)


def compress_video(src):
    if os.path.isfile(src):
        print("Compressing " + src + " with x265 crf 28...")
        subprocess.run(["ffmpeg", "-i", src, "-vcodec", "libx265", "-crf", "28", src + "_temp.mp4",
                        "-loglevel", "panic"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.isfile(src + "_temp.mp4"):
            os.remove(src)
            shutil.move(src + "_temp.mp4", src)


if __name__ == "__main__":
    main()
