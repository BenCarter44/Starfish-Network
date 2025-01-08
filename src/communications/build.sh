python3 -m grpc_tools.protoc -Iprotocol/ --python_out=. --pyi_out=. --grpc_python_out=. protocol/main.proto protocol/primitives.proto
