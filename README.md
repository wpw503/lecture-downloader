# Lecture Downloader
Automatic video downloader based on [this](https://gist.github.com/feryandi/3a9fd566247d936e0e4b86f0da3e19d8) file by [
feryandi](https://gist.github.com/feryandi)
## Installation
``` bash
pip install -r requirements.txt
```
*Note: Windows users may need to download visual studio to install auto-editor, [see here for more information](https://github.com/WyattBlue/auto-editor/blob/master/articles/installing.md#installing-auto-editor)*
## Using
Edit the file called `settings.json` to contain your panopto information:
``` json
{
    "base_url": "https://foo.bar",
    "modules": [
        {
            "folder_name":"alias",
            "folder_name1":"alias1",
            "folder_name2":"alias2"
        }
    ],
    ".ASPXAUTH": "some ASPXAUTH value"
}
```
Where base url looks something like `https://cardiff.cloud.panopto.eu` and your ASPXAUTH is the value of the *.ASPXAUTH* cookie when you visit panopto. (Use inpect element to get this value)

Then, just run:
```
python3 download_lectures.py
```
The unedited video files are stored in `./downloads` and the shortened files are stored in `./short`