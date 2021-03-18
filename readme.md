# PDQ Container

### Description
This project hosts an implementation of Facebook's [PDQ](https://github.com/facebook/ThreatExchange/tree/master/hashing/pdq), 
a perceptual hashing algorithm used for measuring image similarity. A summary of the algorithm is available [here](https://github.com/facebook/ThreatExchange/blob/master/hashing/hashing.pdf).

Please note this is a reference implementation, and is _not_ recommended for use in production systems. 
*** 
### Setup 
Clone/download this project, and build the image:
```console
foo@bar:/foo/PDQContainer/$ docker build -t ailecs/pdqhasher:latest .
```
This can take a while (bandwidth/CPU depending - YMMV), because it installs build-essential and other large(ish) packages, plus cloning and making the PDQ binaries.

```-t ailecs/pdqhasher:latest``` is optional, but does make the next step easier.
 
Once built, the image can be containerised and run using
```console
foo@bar:~/$ docker run  -p 8080:8080 ailecs/pdqhasher:latest
```
If you didn't use ```-t```, you'll need to work out the image ID. This can be done using
```console
foo@bar:~/$ docker image ls
```

Note: This project comes with an ignorable hashset (based on a reduced subset of [Google Open Images](https://storage.googleapis.com/openimages/web/download.html)) as an example and also for your own use. You may find it easier to mount a local directory of hash files and map them to the container thus:
```console 
foo@bar:~/$ docker run  -p 8080:8080 -v /path/to/your/hashsets:/app/python/hashsets ailecs/pdqhasher:latest
```


*** 
### Usage
The container exposes a RESTful API, with swagger 2.0 compliant documentation. This can be accessed via http://localhost:8080/ui . We recommend using this documentation for learning the API.

To hash a file:
```Post``` a file (multipart - named ```file_to_upload``` to http://localhost:8080/pdq/hash . The hash (encoded as a hex string) is returned.

To search for near matches to a file:
```Post``` a file (multipart - named ```file_to_upload``` to http://localhost:8080/pdq . An array of matches (refer swagger doc for specifications) is returned.

***
 ### Licensing
This is released under an MIT licence. External dependencies for the software in this project may be subject to more restrictive arrangements. 

***

### Notes
The service utilises [MIH](https://github.com/AiLECS/pyMIH) for accelerating lookups within the configured hamming distance. Otherwise, it uses linear search.
You *will* encounter performance drops with linear search, particularly as your dataset grows!
