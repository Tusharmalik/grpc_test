import os
import re
import sys
import glob
import subprocess
import importlib
from jinja2 import Template

def readArg():
    if len(sys.argv) == 2:
        proto_file_path = str(sys.argv[1])
        if os.path.isfile(proto_file_path):
            return proto_file_path
        else:
            raise FileNotFoundError
    else:
        print("There must be two arguments passed: \
        1. Name of the script file, \
        2. Name of the proto file")
        raise ValueError("arg not found")
    
    
def createTemplateFiles(proto_file_name):
    command_status = os.system(
        f"python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. {proto_file_name}"
    )
    if(command_status!=0):
        raise Exception(f"{proto_file_name} syntax not correct")
    

def readProtoFile(filename):
    with open(f"{filename}.proto", 'r') as r:
        splited_list = []
        file_text = r.read()
        rpc_text = re.findall('rpc .*?\{.*?\}?', file_text, re.S)
        for sentence in rpc_text:
            splited_list.append(sentence.split(' '))

    return splited_list


def rpc_dict(filename):
    with open(f"{filename}.proto", 'r') as r:
    rpc_dict = {
        "func": "",
        "stream_req": False,
        "req_message_name": "",
        "req_message_param": [],
        "stream_res": False,
        "res_message_name": "",
        "res_message_param": []
    }
    file_text = r.read()
    without_comments_text = re.sub(r'//.*\n', '', file_text)
    rpc_text = re.findall('rpc .*?\{.*?\}?', file_text, re.S)
    
    for sentence in rpc_text:
        sentence = sentence.split(" ")
        rpc_dict["func"] = sentence[1]
        rpc_dict["req_message_name"] = sentence[2]
        rpc_dict["res_message_name"] = sentence[4]
    
    message_text = re.findall('message .*?\{.*?\}', without_comments_text, re.S)
    for sentence in message_text:
        message_text = sentence.replace("\n", '').split("{")
        messageBody = re.findall('\S+', message_text[0].strip())[-1]
        message_text = re.findall('\S+', message_text[1].strip())
        for i in range(len(message_text)):
            if rpc_dict.get("req_message_name") == message_text[1]:
                if message_text[i] == "=":
                    rpc_dict["req_message_param"].append(message_text[i-1])
            elif rpc_dict.get("res_message_name") == message_text[1]:
                if message_text[i] == "=":
                    rpc_dict["res_message_param"].append(message_text[i-1])
            else:
                pass
    return rpc_dict

def createServerTemplate(filename):
    import_pb2_file = f"{ filename }_pb2"
    splited_list_file = readProtoFile(filename)
    rpc_dict = rpc_dict(filename)
    response_dict = {i:"" for i in rpc_dict["res_message_param"]}
    request_dict = {i:"" for i in rpc_dict["req_message_param"]}

    pb2_file_obj = importlib.import_module(import_pb2_file)
    server_template = """
    from concurrent import futures
    import logging

    import grpc

    import {{ filename }}_pb2
    import {{ filename }}_pb2_grpc

    class {{ service }}({{ filename }}_pb2_grpc.{{ service }}Servicer):

        {% for item in rpc_list %}
        def {{ item[1] }}(self, request, context):
            return {{ filename }}_pb2.{{ item[4] }}({{ response_dict }})
        {% endfor %}


    def serve():
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        {{ filename }}_pb2_grpc.add_{{ service }}Servicer_to_server({{ service }}(), server)
        server.add_insecure_port('[::]:50051')
        server.start()
        server.wait_for_termination()


    if __name__ == '__main__':
        logging.basicConfig()
        serve()
    """
    template = Template(server_template)
    server_template = template.render(
        filename=filename, 
        service=pb2_file_obj.DESCRIPTOR.services_by_name.keys()[0], 
        rpc_list=splited_list_file,
        response_dict=**response_dict)
    
    with open("server.py", "w") as f:
        f.write(server_template)

def createClientTemplate():
    import_pb2_file = f"{ filename }_pb2"
    splited_list_file = readProtoFile(filename)
    rpc_dict = rpc_dict(filename)
    response_dict = {i:"" for i in rpc_dict["res_message_param"]}
    request_dict = {i:"" for i in rpc_dict["req_message_param"]}

    pb2_file_obj = importlib.import_module(import_pb2_file)
    client_template = """
    from __future__ import print_function
    import logging

    import grpc

    import {{ filename }}_pb2
    import {{ filename }}_pb2_grpc


    def run():
        # NOTE(gRPC Python Team): .close() is possible on a channel and should be
        # used in circumstances in which the with statement does not fit the needs
        # of the code.
        with grpc.insecure_channel('localhost:50051') as channel:
            stub = {{ filename }}_pb2_grpc.{{ service }}Stub(channel)
            {% for item in rpc_list %}
            response = stub.SayHello({{ filename }}_pb2.HelloRequest(name='your'))
            {% endfor %}
        
        print("{{ service }} client received1: " + response1.message)


    if __name__ == '__main__':
        logging.basicConfig()
        run()
    """

    template = Template(client_template)
    client_template = template.render(
        filename=filename, 
        service=pb2_file_obj.DESCRIPTOR.services_by_name.keys()[0], 
        rpc_list=splited_list_file,
        response_dict=**request_dict)
    
    with open("client.py", "w") as f:
        f.write(client_template)


if __name__ == "__main__":
    proto_file_path = readArg()
    proto_file_name = proto_file_path.strip().split("/")[-1]
    createTemplateFiles(proto_file_name)
    proto_file_name_without_extension, ext = os.path.splitext(proto_file_name)
    createServerTemplate(proto_file_name_without_extension)
    