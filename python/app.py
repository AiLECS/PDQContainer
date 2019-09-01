import connexion
from PIL import Image
from io import BytesIO
import os
import subprocess
import tempfile
import logging
from timeit import default_timer as timer

hasher = '/facebook/hashing/pdq/cpp/pdq-photo-hasher'

# returns each hash value provided for each unique file name
def getHashes(output):
    vals = {}
    output = str(output, 'utf-8').splitlines()
    for line in output:
        v = line.split(',')
        fn = os.path.splitext(os.path.basename(v[2]))[0]
        if fn in vals:
            vals[fn].append(v[0])
        else:
            vals[fn] = [v[0]]
    return vals


# accepts image file from multipart form, opens as image, thumbnails to 512px long dimension and then calls hasher
# Thumbnailing not strictly required, but used as step towards removing proprietary/licensed dependency in PDQ/TMK
def image_post():
    start = timer()
    with tempfile.TemporaryDirectory() as tempDir:
        try:
            image = Image.open(BytesIO(connexion.request.files['file_to_upload'].read()))
            imagePath = os.path.join(tempDir, 'image.' + image.format)
            image.thumbnail((512, 512))
            image.save(imagePath)
            val = getHashes(subprocess.run([hasher] + [imagePath], capture_output=True).stdout)['image'][0]
            logging.info('Successfully calculated PDQ in ' + str(timer()) + ' seconds')
            return val, 200
        except IOError as e:
            print(e)
            logging.info('Failed to parse file as image')
            return 'Unable to parse file as image', 400
        finally:
            os.unlink(imagePath)


app = connexion.App(__name__, specification_dir='.')
app.add_api('pdqHasher.yaml')
application = app.app

if __name__ == '__main__':
    print('Booting. Using PDQ hasher located at', hasher)
    app.run(port=8080, server='gevent')
