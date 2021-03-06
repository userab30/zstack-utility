'''

@author: yyk
'''

import linux

class IpAddress(object):
    '''
    Help to save and compare IP Address. 
    '''
    def __init__(self, ip):
        self.ip_list = ip.split('.', 3)
        self.ips = []
        for item in self.ip_list:
            if not item.isdigit():
                raise Exception('%s is not digital' % item)
            if int(item) > 255 or item < 0:
                raise Exception('%s must be >=0 and <=255' % item)
            self.ips.append(int(item))

    def __cmp__(self, ip2):
        index = 0
        while index < 4:
            cmp_ret = cmp(self.ips[index], ip2.ips[index])
            if cmp_ret > 0:
                return 1
            elif cmp_ret < 0:
                return -1
            index += 1
        else:
            return 0

    def __gt__(self, ip2):
        if self.__cmp__(ip2) > 0:
            return True
        return False

    def __lt__(self, ip2):
        if self.__cmp__(ip2) < 0:
            return True
        return False

    def __eq__(self, ip2):
        if self.__cmp__(ip2) == 0:
            return True
        return False

    def __le__(self, ip2):
        if self.__cmp__(ip2) > 0:
            return False
        return True

    def __ge__(self, ip2):
        if self.__cmp__(ip2) < 0:
            return False
        return True

    def __str__(self):
        return '.'.join(self.ip_list)

    def __repr__(self):
        return self.__str__()

    def toInt32(self):
        ip32 = self.ips[0];
        for item in self.ips[1:]:
            ip32 = ip32 << 8
            ip32 += item
        return ip32

    def toCidr(self, netmask):
        ip32 = self.toInt32()
        mask32 = IpAddress(netmask).toInt32()
        cidr32 = ip32 & mask32
        cidr = [cidr32 >> 24, (cidr32 & 0x00FF0000) >> 16, (cidr32 & 0x0000FF00) >> 8, cidr32 & 0x00000FF]

        maskbits = linux.netmask_to_cidr(netmask)

        return '%s.%s.%s.%s/%s' % (cidr[0], cidr[1], cidr[2], cidr[3], maskbits)

class Ipv6Address(object):
        '''
        Help to save and compare IP Address.
        '''

        def __init__(self, ip):
            # ipv6 address includes 8 strings
            self.ips = ["", "", "", "", "", "", "", ""]
            self.prefix = ["", "", "", "", "", "", "", ""]
            temp = ip.split('::')
            pos = 0
            for item in temp[0].split(":"):
                self.ips[pos] = item
                self.prefix[pos] = item
                pos = pos + 1

            if len(temp) == 2:
                addr = temp[1].split(":")
                addr_len = len(addr)
                pos = 8 - addr_len
                for item in addr:
                    self.ips[pos] = item
                    pos = pos + 1

        def get_solicited_node_multicast_address(self):
            ip = "ff02::1:ff"
            if len(self.ips[6]) >= 2:
                ip += self.ips[6][-2:]
            else:
                ip += self.ips[6]
            return ip + ":" + self.ips[7]

        def get_prefix(self, prefixlen):
            temp = []
            for item in self.prefix:
                if item != "":
                    temp.append(item)

            return ":".join(temp) + "::/" + str(prefixlen)

def get_link_local_address(mac):
    ''' get ipv6 link local address from 48bits mac address,
        details are described at the https://tools.ietf.org/html/rfc4291#section-2.5.1
        for example mac address 00:01:02:aa:bb:cc
        step 1. inverting the universal/local bit of mac address to 02:01:02:0a:0b:0c
        step 2. insert fffe in the middle of mac address to 02:01:02:ff:fe:0a:0b:0c
        step 3. convert to ip address with fe80::/64, strip the leading '0' in each sector between ':'
                fe80::201:2ff:fe0a:b0c
    '''
    macs = mac.strip("\n").split(":")

    # step 1. inverting the "u" bit of mac address
    macs[0] = hex(int(macs[0], 16) ^ 2)[2:]

    # step 2, insert "fffe"
    part1 = macs[0] + macs[1] + ":"
    part2 = macs[2] + "ff" + ":"
    part3 = "fe" + macs[3] + ":"
    part4 = macs[4] + macs[5]

    #step 3
    return "fe80::" + part1.lstrip("0") + part2.lstrip("0") + part3.lstrip("0") + part4.lstrip("0")
