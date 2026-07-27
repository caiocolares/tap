import os
import pika
import json
import urllib.request
import urllib.error
import time

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
APP_URL = os.environ.get("APP_URL", "http://app:8000/internal/worker")

def callback(ch, method, properties, body):
    payload = body.decode('utf-8')
    print(f"[*] Recebido: {payload}")
    
    # Faz uma requisição POST para a API interna simulando o Knative Eventing
    req = urllib.request.Request(APP_URL, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print(f"[+] Processado com sucesso: {payload}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                print(f"[-] Erro da API: Status {response.status}")
                # Na prática, requisições que não dão 200 deveriam ir para DLQ
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except urllib.error.URLError as e:
        print(f"[-] Falha ao contactar a API: {e}")
        # A API pode estar fora, então colocamos de volta na fila
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    # Aguarda o RabbitMQ estar pronto
    connection = None
    for i in range(10):
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            break
        except pika.exceptions.AMQPConnectionError:
            print("RabbitMQ não disponível. Tentando novamente em 3 segundos...")
            time.sleep(3)
            
    if not connection:
        print("Erro: Não foi possível conectar ao RabbitMQ.")
        return

    channel = connection.channel()
    channel.queue_declare(queue='transcription_jobs', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='transcription_jobs', on_message_callback=callback)

    print('[*] Worker iniciado. Aguardando mensagens. Para sair pressione CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrompido')
