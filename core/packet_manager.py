import hashlib
import json

PACKET_SIZE = 4096 # 4KB chunks

def create_packets(data: str) -> list:
    """Chunks data and adds checksum for integrity."""
    encoded = data.encode('utf-8')
    chunks = [encoded[i:i+PACKET_SIZE] for i in range(0, len(encoded), PACKET_SIZE)]
    
    packets = []
    for i, chunk in enumerate(chunks):
        packets.append({
            "seq": i,
            "total": len(chunks),
            "data": chunk.decode('latin-1'), # Encode for JSON
            "checksum": hashlib.md5(chunk).hexdigest()
        })
    return packets

def verify_packet(packet: dict) -> bool:
    """Verifies packet integrity."""
    data = packet["data"].encode('latin-1')
    return hashlib.md5(data).hexdigest() == packet["checksum"]
