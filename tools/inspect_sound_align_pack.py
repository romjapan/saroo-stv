"""Check generated M68K packing veneer and its native branch contract."""
import re


def validate_patch(driver,source):
    if len(driver)>0x1e00 or driver[0x1256:0x125c]!=bytes.fromhex('d08651cfffbe'):
        raise ValueError('Original driver patch contract mismatch')
    def words(name,count):
        match=re.search(r'\b'+name+r'\['+str(count)+r'\]\s*=\s*\{([^}]+)\}',source)
        if not match:
            raise ValueError('Missing patch array '+name)
        values=[int(v.strip(),0) for v in match[1].split(',')]
        if len(values)!=count:
            raise ValueError('Invalid patch array '+name)
        return b''.join(v.to_bytes(2,'big') for v in values)
    stub=words('stub',10)
    if stub!=bytes.fromhex('d08652800280fffffffe51cff40c4ef90000125c'):
        raise ValueError('Unexpected veneer')
    if 0x1e0c+int.from_bytes(stub[12:14],'big',signed=True)!=0x1218:
        raise ValueError('Wrong DBRA destination')
    if words('original',3)!=driver[0x1256:0x125c] or words('jump',3)!=bytes.fromhex('4ef900001e00'):
        raise ValueError('Unexpected patch site')
    return dict(stub_address=0x1e00,return_address=0x125c,loop_address=0x1218)
