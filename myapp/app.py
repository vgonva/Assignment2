from flask import Flask, Response, render_template, request
import json
from subprocess import Popen, PIPE
import os
from tempfile import mkdtemp
from werkzeug import secure_filename

app = Flask(__name__)


@app.route("/")
def index():
    return """
Available API endpoints:
GET /containers                     List all containers
GET /containers?state=running      List running containers (only)
GET /containers/<id>                Inspect a specific container
GET /containers/<id>/logs           Dump specific container logs
GET /images                         List all images
POST /images                        Create a new image
POST /containers                    Create a new container
PATCH /containers/<id>              Change a container's state
PATCH /images/<id>                  Change a specific image's attributes
DELETE /containers/<id>             Delete a specific container
DELETE /containers                  Delete all containers (including running)
DELETE /images/<id>                 Delete a specific image
DELETE /images                      Delete all images
"""


@app.route('/containers', methods=['GET'])
def containers_index():
    """
    List all containers
    curl -s -X GET -H 'Accept: application/json' http://localhost:8080/containers | python -mjson.tool
    curl -s -X GET -H 'Accept: application/json' http://localhost:8080/containers?state=running | python -mjson.tool
    """
    if request.args.get('state') == 'running':
        output = docker('ps')
        resp = json.dumps(docker_ps_to_array(output))

    else:
        output = docker('ps', '-a')
        resp = json.dumps(docker_ps_to_array(output))

    # resp = ''
    return Response(response=pp_json(resp), mimetype="application/json")


@app.route('/images', methods=['GET'])
def images_index():
    """
    List all images
    Complete the code below generating a valid response.
    curl -s -X GET -H 'Accept: application/json' http://35.189.108.29:5000/images | python -mjson.tool
    """

    command = docker('images')
    array = docker_images_to_array(command)
    resp = json.dumps(array)
    return Response(response=pp_json(resp), mimetype="application/json")



@app.route('/containers/<id>', methods=['GET'])
def containers_show(id):
    """
    Inspect specific container
    curl -s -X GET -H 'Accept: application/json'http://35.189.108.29:5000/containers/idOfContainer | python -mjson.tool
    """
    resp = docker('inspect', id)
    return Response(response=resp, mimetype="application/json")

@app.route('/containers/<id>/logs', methods=['GET'])
def containers_log(id):
    """
    Dump specific container logs
    curl -s -X GET -H 'Accept: application/json' http://35.189.108.29:5000/containers/idOfContainer/logs | python -mjson.tool
    """
    command = docker('logs', id)
    objects = docker_logs_to_object(id,command)
    resp = json.dumps(objects)
    return Response(response=pp_json(resp), mimetype="application/json")

@app.route('/services', methods=['GET'])
def get_services():
    command = docker('service', 'ls')
	arrays=docker_services_to_array(command)
    resp = json.dumps(arrays)
    return Response(response=pp_json(resp), mimetype="application/json")


@app.route('/nodes', methods=['GET'])
def get_nodes():

    command = docker('node', 'ls')
	arrayn=docker_nodes_to_array(command)
    resp = json.dumps(arrayn)
    return Response(response=resp, mimetype="application/json")


@app.route('/images/<id>', methods=['DELETE'])
def images_remove(id):
    """
    Delete a specific image
    curl -s -X DELETE -H 'Content-Type: application/json'  http://35.189.108.29:5000/images/idOfImage
    """
    docker ('rmi', id)
    resp = '{"ID of removed image": "%s"}' % id
  
    return Response(response=resp, mimetype="application/json")


@app.route('/containers/<id>', methods=['DELETE'])
def containers_remove(id):
    """
    Delete a specific container - must be already stopped/killed
    curl -s -X DELETE -H 'Content-Type: application/json' http://35.189.108.29:5000/IDofcontainer
    """
    docker('rm', id)
    resp = '{"ID of removed container": "%s"}' % id
    return Response(response=resp, mimetype="application/json")


@app.route('/containers', methods=['DELETE'])
def containers_remove_all():
    """
    Force remove all containers - dangrous!
    curl -s -X DELETE -H 'Content-Type: application/json'  http://35.189.108.29:5000/containers
    """
    command = docker_ps_to_array(docker('ps', '-a'))
  
    for i in command:
	  #deletes all containers It stops them and then remove it.
        docker('stop', i['id'])
        docker('rm', i['id'])

    resp = '{"Information:": "%s"}' % 'All containers were deleted'
   
    return Response(response=resp, mimetype="application/json")


@app.route('/images', methods=['DELETE'])
def images_remove_all():
    """
    Force remove all images - dangerous!
    curl -s -X DELETE -H 'Content-Type: application/json' http://35.189.108.29:5000/images
	It deletes all images if these one are not running as a container
    """
    command = docker_images_to_array(docker('images'))
    for i in command:
        docker('rmi', i['name'])
    resp = '{"Information:": "%s"}' % 'All images were deleted'
    return Response(response=resp, mimetype="application/json")


@app.route('/containers', methods=['POST'])
def containers_create():
    """
    Create container (from existing image using id or name)
    curl -X POST -H 'Content-Type: application/json' http://35.189.108.29:5000/containers -d '{"image": "77d1809f3481"}'
    """
    body = request.get_json(force=True)
    image = body['image']
    
    id = docker('run', '-d', image)[0:12]
	
    return Response(response='{"id": "%s"}' % id, mimetype="application/json")


@app.route('/images', methods=['POST'])
def images_create():
    """
    Create image (from uploaded Dockerfile)
    curl -H 'Accept: application/json' -F "file=@./lab5-todo-repo/Dockerfile" http://35.189.108.29:5000/images
    """
    dockerfile = request.files['file']
    dockerfile.save ('Dockerfile')
    
    docker ('build', '-t', 'my_new_image', '.')
    new_image = docker_images_to_array(docker('images'))
    
    resp = '{"New image created with ID": "%s"}' % new_image[0]['id']
    
    return Response(response=resp, mimetype="application/json")


@app.route('/containers/<id>', methods=['PATCH'])
def containers_update(id):
    """
    Update container attributes (support: state=running|stopped)
    curl -X PATCH -H 'Content-Type: application/json' http://35.189.108.29:5000/containers/b6cd8ea512c8 -d '{"state": "running"}'
    curl -X PATCH -H 'Content-Type: application/json'  http://35.189.108.29:5000/containers/b6cd8ea512c8 -d '{"state": "stopped"}'
    """
    body = request.get_json(force=True)
    try:
        state = body['state']
        if state == 'running':
            docker('restart', id)
        else:
            docker('stop', id)
    except:
        pass

    resp = '{"id": "%s"}' % id
   
    return Response(response=resp, mimetype="application/json")


@app.route('/images/<id>', methods=['PATCH'])
def images_update(id):
    """
    Update image attributes (support: name[:tag])  tag name should be lowercase only
    curl -s -X PATCH -H 'Content-Type: application/json'  http://35.189.108.29:5000/images/7f2619ed1768 -d '{"tag": "test:1.0"}'
    """
    body = request.get_json(force=True)
    new_tag = body['tag']
    docker('tag', id, new_tag)
    resp = '{"id": "%s"}' % id 
    return Response(response=resp, mimetype="application/json")




def docker(*args):
    cmd = ['docker']
    for sub in args:
        cmd.append(sub)
    process = Popen(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    err = stderr.decode('utf-8')
    out = stdout.decode('utf-8')
    if err.startswith('Error'):
        print('Error: {0} -> {1}'.format(' '.join(cmd), stderr))
    return err + out


#
# Docker output parsing helpers
#

#
# Parses the output of a Docker PS command to a python List
#
def docker_ps_to_array(output):
    all = []
    for c in [line.split() for line in output.splitlines()[1:]]:
        each = {}
        each['id'] = c[0]
        each['image'] = c[1]
        each['name'] = c[-1]
        each['ports'] = c[-2]
        all.append(each)
    return all


#
# Parses the output of a Docker logs command to a python Dictionary
# (Key Value Pair object)
def docker_logs_to_object(id, output):
    logs = {}
    logs['id'] = id
    all = []
    for line in output.splitlines():
        all.append(line)
    logs['logs'] = all
    return logs


#
# Parses the output of a Docker image command to a python List
#
def docker_images_to_array(output):
    all = []
    for c in [line.split() for line in output.splitlines()[1:]]:
        each = {}
        each['id'] = c[2]
        each['tag'] = c[1]
        each['name'] = c[0]
        all.append(each)
    return all

def docker_nodes_to_array(output):
    all = []
    for c in [line.split() for line in output.splitlines()[1:]]:
        each = {}
        each['id'] = c[0]
        each['hostname'] = c[1]
        each['status'] = c[2]
        each['available'] = c[3]
        all.append(each)
    return all
	
def docker_services_to_array(output):
    all = []
    for c in [line.split() for line in output.splitlines()[1:]]:
        each = {}
        each['id'] = c[0]
        each['name'] = c[1]
        each['mode'] = c[2]
        each['replicas'] = c[3]
        each['image'] = c[4]
        all.append(each)
    return all

#Indentation style for json output. It display the output in an easy to read way.
def pp_json(json_thing, sort=True, indents=4):
    if type(json_thing) is str:
        pp = (json.dumps(json.loads(json_thing), sort_keys=sort, indent=indents))
    else:
        pp = (json.dumps(json_thing, sort_keys=sort, indent=indents))
    return pp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
