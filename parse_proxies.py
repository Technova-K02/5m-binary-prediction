#!/usr/bin/env python3
"""Parse proxy list and convert to proper format."""

raw_proxies = """residential.pingproxies.com:8486:84197_ZnVQz_c_gb_asn_5378_m_general_s_LZP4VEGCAE60TYJX:VipdyD0Y4oresidential.pingproxies.com:8801:84197_ZnVQz_c_gb_asn_5378_m_general_s_ZBTQ8BCWR6HH11Q3:VipdyD0Y4oresidential.pingproxies.com:8200:84197_ZnVQz_c_gb_asn_5378_m_general_s_FIDFJE5OVZJSTYEF:VipdyD0Y4oresidential.pingproxies.com:8013:84197_ZnVQz_c_gb_asn_5378_m_general_s_B7SJ4HN8SB7CVHG8:VipdyD0Y4oresidential.pingproxies.com:8138:84197_ZnVQz_c_gb_asn_5378_m_general_s_SNB0LJ8CGDRGKZLO:VipdyD0Y4oresidential.pingproxies.com:8361:84197_ZnVQz_c_gb_asn_5378_m_general_s_5THI0JGHBJLUZGDN:VipdyD0Y4oresidential.pingproxies.com:8193:84197_ZnVQz_c_gb_asn_5378_m_general_s_TQL099HTB9CHY11Z:VipdyD0Y4oresidential.pingproxies.com:8489:84197_ZnVQz_c_gb_asn_5378_m_general_s_3R6B29ZXZY2ZRTUI:VipdyD0Y4oresidential.pingproxies.com:8967:84197_ZnVQz_c_gb_asn_5378_m_general_s_ZLRBP8TLKP62HQ6V:VipdyD0Y4oresidential.pingproxies.com:8749:84197_ZnVQz_c_gb_asn_5378_m_general_s_L18O8223GBGS7QYC:VipdyD0Y4oresidential.pingproxies.com:8961:84197_ZnVQz_c_gb_asn_5378_m_general_s_U8P9E74TFFCS8CZ2:VipdyD0Y4oresidential.pingproxies.com:8663:84197_ZnVQz_c_gb_asn_5378_m_general_s_2O61YHRF95CPEBI3:VipdyD0Y4oresidential.pingproxies.com:8099:84197_ZnVQz_c_gb_asn_5378_m_general_s_NS1I5DUGA127BS6Y:VipdyD0Y4oresidential.pingproxies.com:8172:84197_ZnVQz_c_gb_asn_5378_m_general_s_G1OVDCBFCRPIBUY8:VipdyD0Y4oresidential.pingproxies.com:8667:84197_ZnVQz_c_gb_asn_5378_m_general_s_PJ4BWT0XXQENM0DY:VipdyD0Y4oresidential.pingproxies.com:8548:84197_ZnVQz_c_gb_asn_5378_m_general_s_RQAY3D4CLFFMJVMN:VipdyD0Y4oresidential.pingproxies.com:8427:84197_ZnVQz_c_gb_asn_5378_m_general_s_UFOR7ILT9Z1YHG35:VipdyD0Y4oresidential.pingproxies.com:8608:84197_ZnVQz_c_gb_asn_5378_m_general_s_WXTXOGVZIE5YX7LW:VipdyD0Y4oresidential.pingproxies.com:8430:84197_ZnVQz_c_gb_asn_5378_m_general_s_YZ7DB9CS3AQ4BHFC:VipdyD0Y4oresidential.pingproxies.com:8165:84197_ZnVQz_c_gb_asn_5378_m_general_s_PCN2R5EWIQHYOPPT:VipdyD0Y4oresidential.pingproxies.com:8338:84197_ZnVQz_c_gb_asn_5378_m_general_s_JIC0MHVJ8WM2WKFS:VipdyD0Y4oresidential.pingproxies.com:8134:84197_ZnVQz_c_gb_asn_5378_m_general_s_XWYYLMD5YWY0GQG3:VipdyD0Y4oresidential.pingproxies.com:8351:84197_ZnVQz_c_gb_asn_5378_m_general_s_8DI7PPSVPT3DN7CP:VipdyD0Y4o"""

# Split by "residential.pingproxies.com" to find entries
import re

# Find all proxy entries
pattern = r'([^:]+):(\d+):([^:]+):([^r]+)'
matches = re.findall(pattern, raw_proxies)

proxies = []
for match in matches:
    host, port, username, password = match
    # Clean up password (remove trailing text before next entry)
    password = password.split('residential')[0].strip()
    if password:
        proxy = f"http://{username}:{password}@{host}:{port}"
        proxies.append(proxy)

# Write to file
with open('proxies.txt', 'w') as f:
    for proxy in proxies:
        f.write(proxy + '\n')

print(f"Generated {len(proxies)} proxies")
