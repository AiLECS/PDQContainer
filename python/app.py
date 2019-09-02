import configparser
import connexion
from PIL import Image
from io import BytesIO
import os
import subprocess
import tempfile
import logging
from timeit import default_timer as timer
from bitarray import bitarray

hasher = None
config = {}
hashes = {}


# Load PDQ hashes from files, convert to BitArray and keep in memory for querying.
def loadHashes(path):
    h = {}
    print('Traversing', os.path.abspath(path))
    for root, dirs, files in os.walk(path):
        for f in files:
            if os.path.splitext(f)[1].lower() == '.pdq':
                print('Reading from', f)
                subHashes = []
                with open(os.path.join(root, f)) as fi:
                    for line in fi:
                        b = bitarray()
                        b.frombytes(bytes.fromhex(line))
                        subHashes.append(b)
                h[os.path.splitext(f)[0]] = subHashes
            else:
                print('Skipping', f)
    return h

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


# calculate hamming distances for provided hash
def lookupHash(pdqHash, maxDistance=30, fast=True):
    classes = {}
    b = bitarray()
    b.frombytes(bytes.fromhex(pdqHash))
    for k in hashes.keys():
        for v in hashes[k]:
            hd = 0
            for b1, b2 in zip(b, v):
                if b1 != b2:
                    hd += 1
                    if hd > maxDistance:
                        break
            if hd <= maxDistance:
                if fast:
                    classes[k] = hd
                    break
                elif k not in classes.keys() or (k in classes.keys() and classes[k] > hd):
                    classes[k] = hd
    results = []
    for k in classes.keys():
        if fast:
            results.append({'category': k})
        else:
            results.append({'category': k, 'confidence': getConfidence(classes[k])})
    return results


# convert hamming distance into standard enum for confidence
def getConfidence(hd):
    if hd <= 30:
        return 'high'
    elif 30 < hd < 60:
        return 'medium'
    else:
        return 'low'


#create PDQ hash from image passed in buffer
def createHash(buffer):
    start = timer()
    with tempfile.TemporaryDirectory() as tempDir:
        try:
            image = Image.open(buffer)
            imagePath = os.path.join(tempDir, 'image.' + image.format)
            image.thumbnail((512, 512))
            image.save(imagePath)
            global hasher
            print(hasher)
            val = getHashes(subprocess.run([hasher] + [imagePath], capture_output=True).stdout)['image'][0]
            logging.info('Successfully calculated PDQ in ' + str(timer() - start) + ' seconds')
            return val
        except IOError as e:
            print(e)
            logging.info('Failed to parse file as image')
        finally:
            os.unlink(imagePath)
    return None


# Search for matches to PDQ, using default or provided Hamming Distance as threshold.
def hash_search(pdq, max=30, fast=True):
    val = lookupHash(pdq, maxDistance=max, fast=fast)
    return val, 200


# Search for matches, using uploaded file as source for PDQ
def image_search(file_to_upload, max=30, fast=True):
    buffer = BytesIO(file_to_upload.read())
    val = createHash(buffer)
    if val is not None:
        val = lookupHash(val, maxDistance=max, fast=fast)
        return val, 200
    else:
        return 'Unable to parse file as image', 400


# accepts image file from multipart form, opens as image, thumbnails to 512px long dimension and then calls hasher
# Thumbnailing not strictly required, but used as step towards removing proprietary/licensed dependency in PDQ/TMK
def image_post(file_to_upload):
    buffer = BytesIO(file_to_upload.read())
    val = createHash(buffer)
    if val is not None:
        return val, 200
    else:
        return 'Unable to parse file as image', 400


def startapp(port=8080):
    app = connexion.App(__name__, specification_dir='.')
    app.add_api('pdqHasher.yaml')
    logging.info('Loaded config file at ' + 'pdqHasher.yaml')
    logging.info('Starting server')
    app.run(port=port, server='gevent')


config = configparser.ConfigParser()
config.read('config.ini')
hashBinary = config['PDQ']['Hasher']

hasher = hashBinary
hashes = loadHashes(config['PDQ']['HashDirectory'])
counter = 0

if __name__ == '__main__':
    for k in hashes.keys():
        print(len(hashes[k]), 'hashes loaded for', k)
        logging.info(len(hashes[k]), 'hashes loaded for', k)
        counter += len(hashes[k])
    print(counter, 'total hashes loaded for', len(hashes.keys()), 'classes')
    print('Booting. Using PDQ hasher located at', hasher)
    startapp(port=int(config['NETWORK']['Port']))
    logging.info('Exiting.')
