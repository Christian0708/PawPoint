import bcrypt
import grpc
import os
import json
import uuid
import time
from concurrent import futures
import cloudsecurity_pb2
import cloudsecurity_pb2_grpc
from utils import send_otp, hash_password

class UserServiceSkeleton(cloudsecurity_pb2_grpc.UserServiceServicer):
    def __init__(self):
        self.base_dir = os.path.dirname(__file__)
        self.users_path = os.path.join(self.base_dir, 'users.json')
        self._ensure_store()
        self.pending_otp = {}

    def _ensure_store(self):
        if not os.path.exists(self.users_path):
            try:
                with open(self.users_path, 'w') as f:
                    json.dump({}, f)
            except Exception:
                pass

    def _load_users(self):
        try:
            with open(self.users_path, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_users(self, users):
        try:
            with open(self.users_path, 'w') as f:
                json.dump(users, f, indent=2)
            return True
        except Exception:
            return False

    def CreateUser(self, request, context):
        users = self._load_users()
        if request.login in users:
            return cloudsecurity_pb2.CreateUserResponse(created=False, message="User already exists")
        pwd_hash = hash_password(request.password)
        quota_bytes = int(request.quota_gb) * 1024 * 1024 * 1024
        users[request.login] = {
            'email': request.email,
            'password_hash': pwd_hash,
            'quota_bytes': quota_bytes,
            'used_bytes': 0,
            'files': []
        }
        ok = self._save_users(users)
        return cloudsecurity_pb2.CreateUserResponse(created=ok, message="Created" if ok else "Failed to save")

    def Login(self, request, context):
        users = self._load_users()
        user = users.get(request.login)
        if not user:
            return cloudsecurity_pb2.LoginResponse(result="Unauthorized", pending_id="")
        if not bcrypt.checkpw(request.password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return cloudsecurity_pb2.LoginResponse(result="Unauthorized", pending_id="")
        email = user.get('email')
        # Send OTP in background to avoid blocking
        import threading
        threading.Thread(target=send_otp, args=(email,), daemon=True).start()
        pending_id = str(uuid.uuid4())
        self.pending_otp[request.login] = {
            'pending_id': pending_id,
            'expires_at': time.time() + 300
        }
        return cloudsecurity_pb2.LoginResponse(result="OTP sent", pending_id=pending_id)

    def VerifyOtp(self, request, context):
        # In a real system, we would verify the OTP code persisted server-side
        pending = self.pending_otp.get(request.login)
        if not pending or pending['pending_id'] != request.pending_id or time.time() > pending['expires_at']:
            return cloudsecurity_pb2.AuthToken(token="")
        # Issue a simple opaque token
        token = str(uuid.uuid4())
        return cloudsecurity_pb2.AuthToken(token=token)

    def GetProfile(self, request, context):
        users = self._load_users()
        user = users.get(request.login)
        if not user:
            return cloudsecurity_pb2.Profile(login="", email="", used_bytes=0, quota_bytes=0)
        return cloudsecurity_pb2.Profile(
            login=request.login,
            email=user.get('email', ''),
            used_bytes=int(user.get('used_bytes', 0)),
            quota_bytes=int(user.get('quota_bytes', 0))
        )

    def PrecheckStore(self, request, context):
        users = self._load_users()
        user = users.get(request.login)
        if not user:
            return cloudsecurity_pb2.PrecheckStoreResponse(allowed=False, remaining_bytes=0)
        used = int(user.get('used_bytes', 0))
        quota = int(user.get('quota_bytes', 0))
        remaining = quota - used
        allowed = request.file_size <= remaining
        return cloudsecurity_pb2.PrecheckStoreResponse(allowed=allowed, remaining_bytes=max(0, remaining))

    def AddFileRecord(self, request, context):
        users = self._load_users()
        user = users.get(request.login)
        if not user:
            return cloudsecurity_pb2.AddFileRecordResponse(ok=False)
        rec = request.record
        file_dict = {
            'file_id': rec.file_id,
            'name': rec.name,
            'size': int(rec.size),
            'nodes': list(rec.nodes)
        }
        user['files'] = user.get('files', [])
        user['files'].append(file_dict)
        user['used_bytes'] = int(user.get('used_bytes', 0)) + int(rec.size)
        users[request.login] = user
        ok = self._save_users(users)
        return cloudsecurity_pb2.AddFileRecordResponse(ok=ok)

    def RemoveFileRecord(self, request, context):
        users = self._load_users()
        user = users.get(request.login)
        if not user:
            return cloudsecurity_pb2.RemoveFileRecordResponse(ok=False)
        files = user.get('files', [])
        files = [f for f in files if f.get('file_id') != request.file_id]
        user['files'] = files
        user['used_bytes'] = max(0, int(user.get('used_bytes', 0)) - int(request.size))
        users[request.login] = user
        ok = self._save_users(users)
        return cloudsecurity_pb2.RemoveFileRecordResponse(ok=ok)
    
    def ListAllUsers(self, request, context):
        """List all registered users"""
        users = self._load_users()
        user_list = []
        for login, user_data in users.items():
            user_info = cloudsecurity_pb2.UserInfo(
                login=login,
                email=user_data.get('email', ''),
                used_bytes=int(user_data.get('used_bytes', 0)),
                quota_bytes=int(user_data.get('quota_bytes', 0)),
                file_count=len(user_data.get('files', []))
            )
            user_list.append(user_info)
        return cloudsecurity_pb2.ListAllUsersResponse(users=user_list)
    
    def UpdateUserQuota(self, request, context):
        """Update user's storage quota"""
        users = self._load_users()
        if request.login not in users:
            return cloudsecurity_pb2.UpdateUserQuotaResponse(ok=False, message="User not found")
        
        quota_bytes = int(request.quota_gb) * 1024 * 1024 * 1024
        users[request.login]['quota_bytes'] = quota_bytes
        ok = self._save_users(users)
        message = f"Quota updated to {request.quota_gb} GB" if ok else "Failed to update quota"
        return cloudsecurity_pb2.UpdateUserQuotaResponse(ok=ok, message=message)

    def ListFiles(self, request, context):
        users = self._load_users()
        user = users.get(request.login)
        recs = []
        if user:
            for f in user.get('files', []):
                recs.append(
                    cloudsecurity_pb2.FileRecord(
                        file_id=f.get('file_id', ''),
                        name=f.get('name', ''),
                        size=int(f.get('size', 0)),
                        nodes=f.get('nodes', [])
                    )
                )
        return cloudsecurity_pb2.ListFilesResponse(records=recs)

def run():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    cloudsecurity_pb2_grpc.add_UserServiceServicer_to_server(UserServiceSkeleton(), server)
    server.add_insecure_port('[::]:51234')
    print('Starting Server on port 51234 ............', end='')
    server.start()
    print('[OK]')
    server.wait_for_termination()

if __name__ == '__main__':
    run()
