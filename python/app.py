import configparser
import connexion
from PIL import Image
from io import BytesIO
import os
import subprocess
import tempfile
import logging
from timeit import default_timer as timer
import multiprocessing
from pyMIH import MIHIndex
import functools

hasher = None
config = {}
index = None
maxHamming = None
workers = round(multiprocessing.cpu_count()/2)


# Load PDQ hashes from files, convert to BitArray and keep in memory for querying.
def loadHashes(path, maxHamming):
    x = MIHIndex()
    for root, dirs, files in os.walk(path):
        for f in files:
            if os.path.splitext(f)[1].lower() == '.pdq':
                print('Reading from', f)
                subHashes = []
                with open(os.path.join(root, f)) as fi:
                    for line in fi:
                        if not line.startswith('#'):
                            subHashes.append(line.strip())
                x.update(subHashes, os.path.splitext(f)[0])
            else:
                print('Skipping', f)
    print('Training index')
    x.train(16, int(maxHamming))
    print('Finished training index')
    return x

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


# Check hamming distance - iterate through list
def checkhamming(pdqHash, hashList, maxDistance, fast):
    best = len(pdqHash)
    for h in hashList:
        hd = 0
        for b1, b2 in zip(pdqHash, h):
            if b1 != b2:
                hd += 1
                if hd > maxDistance:
                    break
        if hd < best:
            best = hd
            if fast and best <= maxDistance:
                return best
    if best <= maxDistance:
        return best
    return None

# calculate hamming distances for provided hash
def multithreadhashlookup(pdqHash, maxDistance=30, fast=True):
    pass
#    classes = {}
#    b = bitarray()
#    b.frombytes(bytes.fromhex(pdqHash))

#    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
#        future_hammings = {executor.submit(checkhamming, b, hashes[category], maxDistance, fast): category for category in hashes.keys()}
#        for future in concurrent.futures.as_completed(future_hammings):
##            hamming = future.result()
 #           if hamming is not None:
 #               if fast:
 #                   classes[k] = hamming
 #                   break
 #               elif k not in classes.keys() or (k in classes.keys() and classes[k] > hamming):
 #                   classes[k] = hamming

 #   results = []
 #   searchTypes = ['full', 'incomplete']
 #   for k in classes.keys():
 #       results.append({'category': k, 'confidence': getConfidence(classes[k]), 'hamming': classes[k],
 #                       'search': searchTypes[fast is True]})
 #   return results


@functools.lru_cache(maxsize=1048576)
# calculate hamming distances for provided hash
def lookupHash(pdqHash, maxDistance=32, fast=True):
    if maxDistance > maxHamming:
        return multithreadhashlookup()

    searchTypes = ['full', 'incomplete']
    results = []
    for p, cats, hamming in index.query(pdqHash):
        results.append({'categories': cats, 'confidence': getConfidence(hamming), 'hamming': hamming, 'search': searchTypes[fast is True]})
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
            # resize as per recommendation in PDQ hashing doc
            image.thumbnail((512, 512))
            image.save(imagePath)
            pdq, quality = runhasher(imagePath)
            logging.info('Successfully calculated PDQ in ' + str(timer() - start) + ' seconds')
            return pdq, quality
        except IOError as e:
            print(e)
            logging.info('Failed to parse file as image')
        finally:
            os.unlink(imagePath)
    return None, None


# Search for matches to PDQ, using default or provided Hamming Distance as threshold.
def hash_search(pdq, max=30, fast=True):
    # val = multithreadhashlookup(pdq, maxDistance=max, fast=fast)
    val = lookupHash(pdq, maxDistance=max, fast=fast)
    return val, 200


# Search for matches, using uploaded file as source for PDQ
def image_search(file_to_upload, max=30, fast=True):
    buffer = BytesIO(file_to_upload.read())
    pdq, quality = createHash(buffer)
    if pdq is not None:
        val = lookupHash(pdq, maxDistance=max, fast=fast)
        return val, 200
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
    index = loadHashes(config['PDQ']['HashDirectory'], config['PDQ']['MaxHamming'])
counter = 0

if config.has_option('GENERAL', 'Workers'):
    workers = int(config['GENERAL']['Workers'])
else:
    logging.info('No Worker count set. Defaulting to cpu count/2 ', workers)

if __name__ == '__main__':
    print('Booting. Using PDQ hasher located at', hasher)
    startapp(port=int(config['NETWORK']['Port']))
    logging.info('Exiting.')
