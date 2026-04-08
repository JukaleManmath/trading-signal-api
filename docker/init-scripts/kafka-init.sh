#!/bin/bash

# Wait until Kafka is fully ready
echo "Waiting for Kafka to be ready..."
sleep 10

# Create topic 'price-events' if it doesn't exist
kafka-topics --bootstrap-server kafka:9092 \
             --create \
             --if-not-exists \
             --topic price-events \
             --replication-factor 1 \
             --partitions 1

kafka-topics --bootstrap-server kafka:9092 \
             --create \
             --if-not-exists \
             --topic price-events-dlq \
             --replication-factor 1 \
             --partitions 1

echo "Kafka topics 'price-events' and 'price-events-dlq' created (if not already existing)"
