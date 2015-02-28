#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tornado
import tornado.ioloop
import tornado.web
import os, uuid
from subprocess import call
import time
import json
from pprint import pprint

from replace import get_presentation_text, translate_list_of_text, translate_power_point
from unbabel.api import UnbabelApi
api = UnbabelApi(username='andre.nascimento.melo',api_key='d7863bba9180c360e76cdc1bccdbae9705427c08',sandbox=True)


def func(room_id):
    print room_id

__UPLOADS__ = "uploads/"

rooms = {"5":
            {"base":"1.html",
            "raw_transcripts_dict":{"0":"és toda louca","1":"fina"},
            "en":
                {"translated_transcripts_dict":
                    {"0":"crazy","1":"thin"}
                }
            ,
            "es":
                {"translated_transcripts_dict":
                    {"0":"loca","1":"magrizima"}
                }
            }
        }
 
class Userform(tornado.web.RequestHandler):
    def get(self,room_id):
        self.render("webspeechdemo.html")

class HomeView(tornado.web.RequestHandler):
    def get(self):
        self.render("home.html")

class CreateView(tornado.web.RequestHandler):
    def get(self,room_id):
        if room_id in rooms:
            self.write("That room is already taken. Please pick a different id.")
        else:
            self.render("fileuploadform.html")

    def post(self,room_id):
        fileinfo = self.request.files['filearg'][0]
        fname = fileinfo['filename']
        extn = os.path.splitext(fname)[1]
        #cname = str(uuid.uuid4()) + extn
        cname = str(room_id)+extn

        call(["mkdir","./uploads/"+room_id])
        fh = open("./uploads/"+room_id+"/"+ cname, 'w')
        fh.write(fileinfo['body'])
        fh.close()
  
        call(["unoconv", "-f", "html", "./uploads/"+room_id+"/"+ cname])

        html_cname = cname.replace("pptx","html")
        rooms[room_id] = {"base":html_cname}
        rooms[room_id]['en'] = {}
        rooms[room_id]['es'] = {}
        print rooms[room_id]["base"]
        self.redirect("/transcript/"+room_id)

class TranscriptView(tornado.web.RequestHandler):
    def get(self,room_id):
        if room_id not in rooms:
            self.redirect("/create/"+room_id)
        else:
            #self.render(rooms[room_id]["base"])
            self.render("transcript.html")

    def post(self,room_id):
        data = json.loads(self.request.body)
        languages = data[0]
        print rooms[room_id]
        raw_transcripts_dict = data[1]
        
        rooms[room_id]["raw_transcripts_dict"] = raw_transcripts_dict
        rooms[room_id]["raw_transcripts_list"] = [value for key,value in raw_transcripts_dict.iteritems()]

        raw_presentation_text=get_presentation_text("./uploads/"+room_id+"/"+room_id+".pptx")
        rooms[room_id]["raw_presentation_text"]=raw_presentation_text
        
        for lang, value in languages.iteritems():
            print lang
            print value

            if value == False:
                continue

            rooms[room_id][lang]["pending_transcripts"] = translate_list_of_text(rooms[room_id]["raw_transcripts_list"], lang, "pt")
            rooms[room_id][lang]["translated_transcripts"] = []

            rooms[room_id][lang]["pending_presentation"] = translate_list_of_text(rooms[room_id]["raw_presentation_text"], lang, "pt")
            rooms[room_id][lang]["translated_presentation"] = []

            print rooms[room_id]["raw_presentation_text"]
            print rooms[room_id]["raw_transcripts_list"]
            
            pprint(rooms[room_id])

            if lang=="es":
                rooms[room_id][lang]["presentation_loop"] = tornado.ioloop.PeriodicCallback(lambda: check_translations(room_id,"presentation", "es"), 5000)
                rooms[room_id][lang]["presentation_loop"].start()
                rooms[room_id][lang]["transcripts_loop"] = tornado.ioloop.PeriodicCallback(lambda: check_translations(room_id,"transcripts", "es"), 5000)
                rooms[room_id][lang]["transcripts_loop"].start()
            elif lang=="en":
                rooms[room_id][lang]["presentation_loop"] = tornado.ioloop.PeriodicCallback(lambda: check_translations(room_id,"presentation", "en"), 5000)
                rooms[room_id][lang]["presentation_loop"].start()
                rooms[room_id][lang]["transcripts_loop"] = tornado.ioloop.PeriodicCallback(lambda: check_translations(room_id,"transcripts", "en"), 5000)
                rooms[room_id][lang]["transcripts_loop"].start()

        pprint(rooms[room_id])

        self.write("success")

class PresentationView(tornado.web.RequestHandler):
    def get(self,room_id):
        if room_id not in rooms:
            self.redirect("/create/"+room_id)
        else:
            #self.render(rooms[room_id]["base"])
            self.render("presentation.html")

class RoomDataView(tornado.web.RequestHandler):
    def get(self,room_id):
        if room_id in rooms:
            self.write(json.dumps(rooms[room_id]))
        else:
            self.write(json.dumps({}))

def check_translations(room_id,kind,lang):
    if kind == "presentation":
        print "entrei presentation " + lang
        completed_translations = []

        for translation_text in rooms[room_id][lang]["pending_presentation"]:
            test=api.get_translation(translation_text.uid)
            print test.status
            if test.status=='completed':
                completed_translations.append(test.translation)

        if len(completed_translations) == len(rooms[room_id][lang]["pending_presentation"]):
            print "ACABOU!!"
            rooms[room_id][lang]["translated_presentation"] = list(completed_translations)
            rooms[room_id][lang]["pending_presentation"] = []
            print rooms[room_id][lang]["translated_presentation"]

            translate_power_point(room_id, rooms[room_id][lang]["translated_presentation"], lang)
            rooms[room_id][lang]["presentation_loop"].stop()
            rooms[room_id][lang]["presentation_loop"] = ""

    elif kind == "transcripts":
        print "entrei transcript " + lang
        completed_translations = []

        for translation_text in rooms[room_id][lang]["pending_transcripts"]:
            test=api.get_translation(translation_text.uid)
            print test.status
            if test.status=='completed':
                completed_translations.append(test.translation)

        if len(completed_translations) == len(rooms[room_id][lang]["pending_transcripts"]):
            print "ACABOU!!"
            rooms[room_id][lang]["translated_transcripts_list"] = list(completed_translations)
            rooms[room_id][lang]["translated_transcripts_dict"] = \
                {key:value for key,value in zip(rooms[room_id]["raw_transcripts_dict"],rooms[room_id][lang]["translated_transcripts_list"])}

            rooms[room_id][lang]["pending_transcripts"] = []
            print rooms[room_id][lang]["translated_transcripts_dict"]

            rooms[room_id][lang]["transcripts_loop"].stop()
            rooms[room_id][lang]["transcripts_loop"] = ""

    else:
        return 

application = tornado.web.Application([
        (r"/create/(?P<room_id>[^\/]+)", CreateView),
        (r"/transcript/(?P<room_id>[^\/]+)", TranscriptView),
        (r"/presentation/(?P<room_id>[^\/]+)", PresentationView),
        (r'/uploads/(.*)', tornado.web.StaticFileHandler, {'path': "./uploads"}),
        (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': "./static"}),
        (r"/data/(?P<room_id>[^\/]+)", RoomDataView),
        (r"/", HomeView),
        ], debug=True)
 
if __name__ == "__main__":
    port = 8888
    application.listen(port)
    print "Listening on port: "+str(port)
    tornado.ioloop.IOLoop.instance().start()