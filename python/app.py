import configparser
import connexion
from PIL import Image
from io import BytesIO
import os
import subprocess
import tempfile
import logging
from pyMIH import MIHIndex
from timeit import default_timer as timer

hasher = None
config = {}
index = None
hashes = None
maxHamming = None


# Load PDQ hashes from files, convert to BitArray and keep in memory for querying.
def loadHashes(path, maxHamming):
    x = MIHIndex()
    hashes = {}
    for root, dirs, files in os.walk(path):
        for f in files:
            if os.path.splitext(f)[1].lower() == '.pdq':
                print('Reading from', f)
                subHashes = set()
                with open(os.path.join(root, f)) as fi:
                    for line in fi:
                        if not line.startswith('#'):
                            subHashes.add(line.strip())
                            if line.strip() not in hashes.keys():
                                hashes[line.strip()] = [os.path.splitext(f)[0]]
                            else:
                                hashes[line.strip()].append(os.path.splitext(f)[0])
                x.update(subHashes, os.path.splitext(f)[0])
            else:
                print('Skipping', f)
    print('Training index')
    x.train(16, int(maxHamming))
    print('Finished training index')
    return x, hashes


# returns PDQ and quality for one passed image file
def runhasher(imagePath):
    try:
        global hasher
        output = str(subprocess.run([hasher] + [imagePath], capture_output=True).stdout, 'utf-8').split(',')
        return output[0], output[1]
    except Exception as e:
        print(e)
        logging.exception("Exception generating PDQ for " + imagePath)
        return None, None


# Lookup hashes within internally mapped memory
def linearhashlookup(pdqHash, maxDistance=30):
    for value, categories in hashes.items():
        hd = MIHIndex.gethamming(pdqHash, value, maxDistance)
        if hd is not None:
            yield pdqHash, categories, hd


# Search for hash value
def lookupHash(pdqHash, maxDistance=32):
    results = []
    if maxDistance > maxHamming:
        for p, cats, hamming in linearhashlookup(pdqHash, maxDistance):
            if hamming <= maxDistance:
                results.append({'pdq': p, 'categories': cats, 'confidence': getConfidence(hamming), 'hamming': hamming})
    elif maxDistance <= maxHamming:
        for p, cats, hamming in index.query(pdqHash):
            if hamming <= maxDistance:
                results.append({'pdq': p, 'categories': cats, 'confidence': getConfidence(hamming), 'hamming': hamming})
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
    with tempfile.TemporaryDirectory() as tempDir:
        try:
            image = Image.open(buffer)
            imagePath = os.path.join(tempDir, 'image.' + image.format)
            # resize as per recommendation in PDQ hashing doc
            image.thumbnail((512, 512))
            image.save(imagePath)
            pdq, quality = runhasher(imagePath)
            return pdq, quality
        except IOError as e:
            print(e)
            logging.info('Failed to parse file as image')
        finally:
            os.unlink(imagePath)
    return None, None


# Search for matches to PDQ, using default or provided Hamming Distance as threshold.
def hash_search(pdq, max=30):
    try:
        val = lookupHash(pdq, maxDistance=max)
    except ValueError as e:
        return 'Submitted hamming distance too high. ', 400
    return val, 200


# Search for matches, using uploaded file as source for PDQ
def image_search(file_to_upload, max=30):
    buffer = BytesIO(file_to_upload.read())
    pdq, quality = createHash(buffer)
    if pdq is not None:
        return hash_search(pdq, max)
    else:
        return 'Unable to parse file as image', 400


# accepts image file from multipart form, opens as image, thumbnails to 512px long dimension and then calls hasher
# Thumbnailing not strictly required, but used as step towards removing proprietary/licensed dependency in PDQ/TMK
def image_post(file_to_upload):
    buffer = BytesIO(file_to_upload.read())
    pdq, quality = createHash(buffer)
    if pdq is not None:
        return {'hash': pdq, 'quality': quality}, 200
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

maxHamming = int(config['PDQ']['MaxHamming'])
if index is None:
    index, hashes = loadHashes(config['PDQ']['HashDirectory'], config['PDQ']['MaxHamming'])
counter = 0

if __name__ == '__main__':
    print('Booting. Using PDQ hasher located at', hasher)
    startapp(port=int(config['NETWORK']['Port']))
    logging.info('Exiting.')
