(() => {
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __commonJS = (cb, mod) => function __require() {
    try {
      return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
    } catch (e) {
      throw mod = 0, e;
    }
  };

  // node_modules/hashmap/hashmap.js
  var require_hashmap = __commonJS({
    "node_modules/hashmap/hashmap.js"(exports, module) {
      (function(factory) {
        if (typeof define === "function" && define.amd) {
          define([], factory);
        } else if (typeof module === "object") {
          var HashMap = module.exports = factory();
          HashMap.HashMap = HashMap;
        } else {
          this.HashMap = factory();
        }
      })(function() {
        function HashMap(other) {
          this.clear();
          switch (arguments.length) {
            case 0:
              break;
            case 1: {
              if ("length" in other) {
                multi(this, Array.prototype.concat.apply([], other));
              } else {
                this.copy(other);
              }
              break;
            }
            default:
              multi(this, arguments);
              break;
          }
        }
        var proto = HashMap.prototype = {
          constructor: HashMap,
          get: function(key) {
            var data = this._data[this.hash(key)];
            return data && data[1];
          },
          set: function(key, value) {
            var hash = this.hash(key);
            if (!(hash in this._data)) {
              this.size++;
            }
            this._data[hash] = [key, value];
          },
          multi: function() {
            multi(this, arguments);
          },
          copy: function(other) {
            for (var hash in other._data) {
              if (!(hash in this._data)) {
                this.size++;
              }
              this._data[hash] = other._data[hash];
            }
          },
          has: function(key) {
            return this.hash(key) in this._data;
          },
          search: function(value) {
            for (var key in this._data) {
              if (this._data[key][1] === value) {
                return this._data[key][0];
              }
            }
            return null;
          },
          delete: function(key) {
            var hash = this.hash(key);
            if (hash in this._data) {
              this.size--;
              delete this._data[hash];
            }
          },
          type: function(key) {
            var str = Object.prototype.toString.call(key);
            var type = str.slice(8, -1).toLowerCase();
            if (!key && (type === "domwindow" || type === "window")) {
              return key + "";
            }
            return type;
          },
          keys: function() {
            var keys = [];
            this.forEach(function(_, key) {
              keys.push(key);
            });
            return keys;
          },
          values: function() {
            var values = [];
            this.forEach(function(value) {
              values.push(value);
            });
            return values;
          },
          entries: function() {
            var entries = [];
            this.forEach(function(value, key) {
              entries.push([key, value]);
            });
            return entries;
          },
          // TODO: This is deprecated and will be deleted in a future version
          count: function() {
            return this.size;
          },
          clear: function() {
            this._data = {};
            this.size = 0;
          },
          clone: function() {
            return new HashMap(this);
          },
          hash: function(key) {
            switch (this.type(key)) {
              case "undefined":
              case "null":
              case "boolean":
              case "number":
              case "regexp":
                return key + "";
              case "date":
                return "\u2663" + key.getTime();
              case "string":
                return "\u2660" + key;
              case "array":
                var hashes = [];
                for (var i = 0; i < key.length; i++) {
                  hashes[i] = this.hash(key[i]);
                }
                return "\u2665" + hashes.join("\u205E");
              default:
                if (!key.hasOwnProperty("_hmuid_")) {
                  key._hmuid_ = ++HashMap.uid;
                  hide(key, "_hmuid_");
                }
                return "\u2666" + key._hmuid_;
            }
          },
          forEach: function(func, ctx) {
            for (var key in this._data) {
              var data = this._data[key];
              func.call(ctx || this, data[1], data[0]);
            }
          }
        };
        HashMap.uid = 0;
        if (typeof Symbol !== "undefined" && typeof Symbol.iterator !== "undefined") {
          proto[Symbol.iterator] = function() {
            var entries = this.entries();
            var i = 0;
            return {
              next: function() {
                if (i === entries.length) {
                  return { done: true };
                }
                var currentEntry = entries[i++];
                return {
                  value: { key: currentEntry[0], value: currentEntry[1] },
                  done: false
                };
              }
            };
          };
        }
        ["set", "multi", "copy", "delete", "clear", "forEach"].forEach(function(method) {
          var fn = proto[method];
          proto[method] = function() {
            fn.apply(this, arguments);
            return this;
          };
        });
        HashMap.prototype.remove = HashMap.prototype.delete;
        function multi(map, args) {
          for (var i = 0; i < args.length; i += 2) {
            map.set(args[i], args[i + 1]);
          }
        }
        function hide(obj, prop) {
          if (Object.defineProperty) {
            Object.defineProperty(obj, prop, { enumerable: false });
          }
        }
        return HashMap;
      });
    }
  });

  // node_modules/big-integer/BigInteger.js
  var require_BigInteger = __commonJS({
    "node_modules/big-integer/BigInteger.js"(exports, module) {
      var bigInt = (function(undefined2) {
        "use strict";
        var BASE = 1e7, LOG_BASE = 7, MAX_INT = 9007199254740992, MAX_INT_ARR = smallToArray(MAX_INT), DEFAULT_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz";
        var supportsNativeBigInt = typeof BigInt === "function";
        function Integer(v, radix, alphabet, caseSensitive) {
          if (typeof v === "undefined") return Integer[0];
          if (typeof radix !== "undefined") return +radix === 10 && !alphabet ? parseValue(v) : parseBase(v, radix, alphabet, caseSensitive);
          return parseValue(v);
        }
        function BigInteger(value, sign) {
          this.value = value;
          this.sign = sign;
          this.isSmall = false;
        }
        BigInteger.prototype = Object.create(Integer.prototype);
        function SmallInteger(value) {
          this.value = value;
          this.sign = value < 0;
          this.isSmall = true;
        }
        SmallInteger.prototype = Object.create(Integer.prototype);
        function NativeBigInt(value) {
          this.value = value;
        }
        NativeBigInt.prototype = Object.create(Integer.prototype);
        function isPrecise(n) {
          return -MAX_INT < n && n < MAX_INT;
        }
        function smallToArray(n) {
          if (n < 1e7)
            return [n];
          if (n < 1e14)
            return [n % 1e7, Math.floor(n / 1e7)];
          return [n % 1e7, Math.floor(n / 1e7) % 1e7, Math.floor(n / 1e14)];
        }
        function arrayToSmall(arr) {
          trim(arr);
          var length = arr.length;
          if (length < 4 && compareAbs(arr, MAX_INT_ARR) < 0) {
            switch (length) {
              case 0:
                return 0;
              case 1:
                return arr[0];
              case 2:
                return arr[0] + arr[1] * BASE;
              default:
                return arr[0] + (arr[1] + arr[2] * BASE) * BASE;
            }
          }
          return arr;
        }
        function trim(v) {
          var i2 = v.length;
          while (v[--i2] === 0) ;
          v.length = i2 + 1;
        }
        function createArray(length) {
          var x = new Array(length);
          var i2 = -1;
          while (++i2 < length) {
            x[i2] = 0;
          }
          return x;
        }
        function truncate(n) {
          if (n > 0) return Math.floor(n);
          return Math.ceil(n);
        }
        function add(a, b) {
          var l_a = a.length, l_b = b.length, r = new Array(l_a), carry = 0, base = BASE, sum, i2;
          for (i2 = 0; i2 < l_b; i2++) {
            sum = a[i2] + b[i2] + carry;
            carry = sum >= base ? 1 : 0;
            r[i2] = sum - carry * base;
          }
          while (i2 < l_a) {
            sum = a[i2] + carry;
            carry = sum === base ? 1 : 0;
            r[i2++] = sum - carry * base;
          }
          if (carry > 0) r.push(carry);
          return r;
        }
        function addAny(a, b) {
          if (a.length >= b.length) return add(a, b);
          return add(b, a);
        }
        function addSmall(a, carry) {
          var l = a.length, r = new Array(l), base = BASE, sum, i2;
          for (i2 = 0; i2 < l; i2++) {
            sum = a[i2] - base + carry;
            carry = Math.floor(sum / base);
            r[i2] = sum - carry * base;
            carry += 1;
          }
          while (carry > 0) {
            r[i2++] = carry % base;
            carry = Math.floor(carry / base);
          }
          return r;
        }
        BigInteger.prototype.add = function(v) {
          var n = parseValue(v);
          if (this.sign !== n.sign) {
            return this.subtract(n.negate());
          }
          var a = this.value, b = n.value;
          if (n.isSmall) {
            return new BigInteger(addSmall(a, Math.abs(b)), this.sign);
          }
          return new BigInteger(addAny(a, b), this.sign);
        };
        BigInteger.prototype.plus = BigInteger.prototype.add;
        SmallInteger.prototype.add = function(v) {
          var n = parseValue(v);
          var a = this.value;
          if (a < 0 !== n.sign) {
            return this.subtract(n.negate());
          }
          var b = n.value;
          if (n.isSmall) {
            if (isPrecise(a + b)) return new SmallInteger(a + b);
            b = smallToArray(Math.abs(b));
          }
          return new BigInteger(addSmall(b, Math.abs(a)), a < 0);
        };
        SmallInteger.prototype.plus = SmallInteger.prototype.add;
        NativeBigInt.prototype.add = function(v) {
          return new NativeBigInt(this.value + parseValue(v).value);
        };
        NativeBigInt.prototype.plus = NativeBigInt.prototype.add;
        function subtract(a, b) {
          var a_l = a.length, b_l = b.length, r = new Array(a_l), borrow = 0, base = BASE, i2, difference;
          for (i2 = 0; i2 < b_l; i2++) {
            difference = a[i2] - borrow - b[i2];
            if (difference < 0) {
              difference += base;
              borrow = 1;
            } else borrow = 0;
            r[i2] = difference;
          }
          for (i2 = b_l; i2 < a_l; i2++) {
            difference = a[i2] - borrow;
            if (difference < 0) difference += base;
            else {
              r[i2++] = difference;
              break;
            }
            r[i2] = difference;
          }
          for (; i2 < a_l; i2++) {
            r[i2] = a[i2];
          }
          trim(r);
          return r;
        }
        function subtractAny(a, b, sign) {
          var value;
          if (compareAbs(a, b) >= 0) {
            value = subtract(a, b);
          } else {
            value = subtract(b, a);
            sign = !sign;
          }
          value = arrayToSmall(value);
          if (typeof value === "number") {
            if (sign) value = -value;
            return new SmallInteger(value);
          }
          return new BigInteger(value, sign);
        }
        function subtractSmall(a, b, sign) {
          var l = a.length, r = new Array(l), carry = -b, base = BASE, i2, difference;
          for (i2 = 0; i2 < l; i2++) {
            difference = a[i2] + carry;
            carry = Math.floor(difference / base);
            difference %= base;
            r[i2] = difference < 0 ? difference + base : difference;
          }
          r = arrayToSmall(r);
          if (typeof r === "number") {
            if (sign) r = -r;
            return new SmallInteger(r);
          }
          return new BigInteger(r, sign);
        }
        BigInteger.prototype.subtract = function(v) {
          var n = parseValue(v);
          if (this.sign !== n.sign) {
            return this.add(n.negate());
          }
          var a = this.value, b = n.value;
          if (n.isSmall)
            return subtractSmall(a, Math.abs(b), this.sign);
          return subtractAny(a, b, this.sign);
        };
        BigInteger.prototype.minus = BigInteger.prototype.subtract;
        SmallInteger.prototype.subtract = function(v) {
          var n = parseValue(v);
          var a = this.value;
          if (a < 0 !== n.sign) {
            return this.add(n.negate());
          }
          var b = n.value;
          if (n.isSmall) {
            return new SmallInteger(a - b);
          }
          return subtractSmall(b, Math.abs(a), a >= 0);
        };
        SmallInteger.prototype.minus = SmallInteger.prototype.subtract;
        NativeBigInt.prototype.subtract = function(v) {
          return new NativeBigInt(this.value - parseValue(v).value);
        };
        NativeBigInt.prototype.minus = NativeBigInt.prototype.subtract;
        BigInteger.prototype.negate = function() {
          return new BigInteger(this.value, !this.sign);
        };
        SmallInteger.prototype.negate = function() {
          var sign = this.sign;
          var small = new SmallInteger(-this.value);
          small.sign = !sign;
          return small;
        };
        NativeBigInt.prototype.negate = function() {
          return new NativeBigInt(-this.value);
        };
        BigInteger.prototype.abs = function() {
          return new BigInteger(this.value, false);
        };
        SmallInteger.prototype.abs = function() {
          return new SmallInteger(Math.abs(this.value));
        };
        NativeBigInt.prototype.abs = function() {
          return new NativeBigInt(this.value >= 0 ? this.value : -this.value);
        };
        function multiplyLong(a, b) {
          var a_l = a.length, b_l = b.length, l = a_l + b_l, r = createArray(l), base = BASE, product, carry, i2, a_i, b_j;
          for (i2 = 0; i2 < a_l; ++i2) {
            a_i = a[i2];
            for (var j = 0; j < b_l; ++j) {
              b_j = b[j];
              product = a_i * b_j + r[i2 + j];
              carry = Math.floor(product / base);
              r[i2 + j] = product - carry * base;
              r[i2 + j + 1] += carry;
            }
          }
          trim(r);
          return r;
        }
        function multiplySmall(a, b) {
          var l = a.length, r = new Array(l), base = BASE, carry = 0, product, i2;
          for (i2 = 0; i2 < l; i2++) {
            product = a[i2] * b + carry;
            carry = Math.floor(product / base);
            r[i2] = product - carry * base;
          }
          while (carry > 0) {
            r[i2++] = carry % base;
            carry = Math.floor(carry / base);
          }
          return r;
        }
        function shiftLeft(x, n) {
          var r = [];
          while (n-- > 0) r.push(0);
          return r.concat(x);
        }
        function multiplyKaratsuba(x, y) {
          var n = Math.max(x.length, y.length);
          if (n <= 30) return multiplyLong(x, y);
          n = Math.ceil(n / 2);
          var b = x.slice(n), a = x.slice(0, n), d = y.slice(n), c = y.slice(0, n);
          var ac = multiplyKaratsuba(a, c), bd = multiplyKaratsuba(b, d), abcd = multiplyKaratsuba(addAny(a, b), addAny(c, d));
          var product = addAny(addAny(ac, shiftLeft(subtract(subtract(abcd, ac), bd), n)), shiftLeft(bd, 2 * n));
          trim(product);
          return product;
        }
        function useKaratsuba(l1, l2) {
          return -0.012 * l1 - 0.012 * l2 + 15e-6 * l1 * l2 > 0;
        }
        BigInteger.prototype.multiply = function(v) {
          var n = parseValue(v), a = this.value, b = n.value, sign = this.sign !== n.sign, abs;
          if (n.isSmall) {
            if (b === 0) return Integer[0];
            if (b === 1) return this;
            if (b === -1) return this.negate();
            abs = Math.abs(b);
            if (abs < BASE) {
              return new BigInteger(multiplySmall(a, abs), sign);
            }
            b = smallToArray(abs);
          }
          if (useKaratsuba(a.length, b.length))
            return new BigInteger(multiplyKaratsuba(a, b), sign);
          return new BigInteger(multiplyLong(a, b), sign);
        };
        BigInteger.prototype.times = BigInteger.prototype.multiply;
        function multiplySmallAndArray(a, b, sign) {
          if (a < BASE) {
            return new BigInteger(multiplySmall(b, a), sign);
          }
          return new BigInteger(multiplyLong(b, smallToArray(a)), sign);
        }
        SmallInteger.prototype._multiplyBySmall = function(a) {
          if (isPrecise(a.value * this.value)) {
            return new SmallInteger(a.value * this.value);
          }
          return multiplySmallAndArray(Math.abs(a.value), smallToArray(Math.abs(this.value)), this.sign !== a.sign);
        };
        BigInteger.prototype._multiplyBySmall = function(a) {
          if (a.value === 0) return Integer[0];
          if (a.value === 1) return this;
          if (a.value === -1) return this.negate();
          return multiplySmallAndArray(Math.abs(a.value), this.value, this.sign !== a.sign);
        };
        SmallInteger.prototype.multiply = function(v) {
          return parseValue(v)._multiplyBySmall(this);
        };
        SmallInteger.prototype.times = SmallInteger.prototype.multiply;
        NativeBigInt.prototype.multiply = function(v) {
          return new NativeBigInt(this.value * parseValue(v).value);
        };
        NativeBigInt.prototype.times = NativeBigInt.prototype.multiply;
        function square(a) {
          var l = a.length, r = createArray(l + l), base = BASE, product, carry, i2, a_i, a_j;
          for (i2 = 0; i2 < l; i2++) {
            a_i = a[i2];
            carry = 0 - a_i * a_i;
            for (var j = i2; j < l; j++) {
              a_j = a[j];
              product = 2 * (a_i * a_j) + r[i2 + j] + carry;
              carry = Math.floor(product / base);
              r[i2 + j] = product - carry * base;
            }
            r[i2 + l] = carry;
          }
          trim(r);
          return r;
        }
        BigInteger.prototype.square = function() {
          return new BigInteger(square(this.value), false);
        };
        SmallInteger.prototype.square = function() {
          var value = this.value * this.value;
          if (isPrecise(value)) return new SmallInteger(value);
          return new BigInteger(square(smallToArray(Math.abs(this.value))), false);
        };
        NativeBigInt.prototype.square = function(v) {
          return new NativeBigInt(this.value * this.value);
        };
        function divMod1(a, b) {
          var a_l = a.length, b_l = b.length, base = BASE, result = createArray(b.length), divisorMostSignificantDigit = b[b_l - 1], lambda = Math.ceil(base / (2 * divisorMostSignificantDigit)), remainder = multiplySmall(a, lambda), divisor = multiplySmall(b, lambda), quotientDigit, shift, carry, borrow, i2, l, q;
          if (remainder.length <= a_l) remainder.push(0);
          divisor.push(0);
          divisorMostSignificantDigit = divisor[b_l - 1];
          for (shift = a_l - b_l; shift >= 0; shift--) {
            quotientDigit = base - 1;
            if (remainder[shift + b_l] !== divisorMostSignificantDigit) {
              quotientDigit = Math.floor((remainder[shift + b_l] * base + remainder[shift + b_l - 1]) / divisorMostSignificantDigit);
            }
            carry = 0;
            borrow = 0;
            l = divisor.length;
            for (i2 = 0; i2 < l; i2++) {
              carry += quotientDigit * divisor[i2];
              q = Math.floor(carry / base);
              borrow += remainder[shift + i2] - (carry - q * base);
              carry = q;
              if (borrow < 0) {
                remainder[shift + i2] = borrow + base;
                borrow = -1;
              } else {
                remainder[shift + i2] = borrow;
                borrow = 0;
              }
            }
            while (borrow !== 0) {
              quotientDigit -= 1;
              carry = 0;
              for (i2 = 0; i2 < l; i2++) {
                carry += remainder[shift + i2] - base + divisor[i2];
                if (carry < 0) {
                  remainder[shift + i2] = carry + base;
                  carry = 0;
                } else {
                  remainder[shift + i2] = carry;
                  carry = 1;
                }
              }
              borrow += carry;
            }
            result[shift] = quotientDigit;
          }
          remainder = divModSmall(remainder, lambda)[0];
          return [arrayToSmall(result), arrayToSmall(remainder)];
        }
        function divMod2(a, b) {
          var a_l = a.length, b_l = b.length, result = [], part = [], base = BASE, guess, xlen, highx, highy, check;
          while (a_l) {
            part.unshift(a[--a_l]);
            trim(part);
            if (compareAbs(part, b) < 0) {
              result.push(0);
              continue;
            }
            xlen = part.length;
            highx = part[xlen - 1] * base + part[xlen - 2];
            highy = b[b_l - 1] * base + b[b_l - 2];
            if (xlen > b_l) {
              highx = (highx + 1) * base;
            }
            guess = Math.ceil(highx / highy);
            do {
              check = multiplySmall(b, guess);
              if (compareAbs(check, part) <= 0) break;
              guess--;
            } while (guess);
            result.push(guess);
            part = subtract(part, check);
          }
          result.reverse();
          return [arrayToSmall(result), arrayToSmall(part)];
        }
        function divModSmall(value, lambda) {
          var length = value.length, quotient = createArray(length), base = BASE, i2, q, remainder, divisor;
          remainder = 0;
          for (i2 = length - 1; i2 >= 0; --i2) {
            divisor = remainder * base + value[i2];
            q = truncate(divisor / lambda);
            remainder = divisor - q * lambda;
            quotient[i2] = q | 0;
          }
          return [quotient, remainder | 0];
        }
        function divModAny(self, v) {
          var value, n = parseValue(v);
          if (supportsNativeBigInt) {
            return [new NativeBigInt(self.value / n.value), new NativeBigInt(self.value % n.value)];
          }
          var a = self.value, b = n.value;
          var quotient;
          if (b === 0) throw new Error("Cannot divide by zero");
          if (self.isSmall) {
            if (n.isSmall) {
              return [new SmallInteger(truncate(a / b)), new SmallInteger(a % b)];
            }
            return [Integer[0], self];
          }
          if (n.isSmall) {
            if (b === 1) return [self, Integer[0]];
            if (b == -1) return [self.negate(), Integer[0]];
            var abs = Math.abs(b);
            if (abs < BASE) {
              value = divModSmall(a, abs);
              quotient = arrayToSmall(value[0]);
              var remainder = value[1];
              if (self.sign) remainder = -remainder;
              if (typeof quotient === "number") {
                if (self.sign !== n.sign) quotient = -quotient;
                return [new SmallInteger(quotient), new SmallInteger(remainder)];
              }
              return [new BigInteger(quotient, self.sign !== n.sign), new SmallInteger(remainder)];
            }
            b = smallToArray(abs);
          }
          var comparison = compareAbs(a, b);
          if (comparison === -1) return [Integer[0], self];
          if (comparison === 0) return [Integer[self.sign === n.sign ? 1 : -1], Integer[0]];
          if (a.length + b.length <= 200)
            value = divMod1(a, b);
          else value = divMod2(a, b);
          quotient = value[0];
          var qSign = self.sign !== n.sign, mod = value[1], mSign = self.sign;
          if (typeof quotient === "number") {
            if (qSign) quotient = -quotient;
            quotient = new SmallInteger(quotient);
          } else quotient = new BigInteger(quotient, qSign);
          if (typeof mod === "number") {
            if (mSign) mod = -mod;
            mod = new SmallInteger(mod);
          } else mod = new BigInteger(mod, mSign);
          return [quotient, mod];
        }
        BigInteger.prototype.divmod = function(v) {
          var result = divModAny(this, v);
          return {
            quotient: result[0],
            remainder: result[1]
          };
        };
        NativeBigInt.prototype.divmod = SmallInteger.prototype.divmod = BigInteger.prototype.divmod;
        BigInteger.prototype.divide = function(v) {
          return divModAny(this, v)[0];
        };
        NativeBigInt.prototype.over = NativeBigInt.prototype.divide = function(v) {
          return new NativeBigInt(this.value / parseValue(v).value);
        };
        SmallInteger.prototype.over = SmallInteger.prototype.divide = BigInteger.prototype.over = BigInteger.prototype.divide;
        BigInteger.prototype.mod = function(v) {
          return divModAny(this, v)[1];
        };
        NativeBigInt.prototype.mod = NativeBigInt.prototype.remainder = function(v) {
          return new NativeBigInt(this.value % parseValue(v).value);
        };
        SmallInteger.prototype.remainder = SmallInteger.prototype.mod = BigInteger.prototype.remainder = BigInteger.prototype.mod;
        BigInteger.prototype.pow = function(v) {
          var n = parseValue(v), a = this.value, b = n.value, value, x, y;
          if (b === 0) return Integer[1];
          if (a === 0) return Integer[0];
          if (a === 1) return Integer[1];
          if (a === -1) return n.isEven() ? Integer[1] : Integer[-1];
          if (n.sign) {
            return Integer[0];
          }
          if (!n.isSmall) throw new Error("The exponent " + n.toString() + " is too large.");
          if (this.isSmall) {
            if (isPrecise(value = Math.pow(a, b)))
              return new SmallInteger(truncate(value));
          }
          x = this;
          y = Integer[1];
          while (true) {
            if (b & true) {
              y = y.times(x);
              --b;
            }
            if (b === 0) break;
            b /= 2;
            x = x.square();
          }
          return y;
        };
        SmallInteger.prototype.pow = BigInteger.prototype.pow;
        NativeBigInt.prototype.pow = function(v) {
          var n = parseValue(v);
          var a = this.value, b = n.value;
          var _0 = BigInt(0), _1 = BigInt(1), _2 = BigInt(2);
          if (b === _0) return Integer[1];
          if (a === _0) return Integer[0];
          if (a === _1) return Integer[1];
          if (a === BigInt(-1)) return n.isEven() ? Integer[1] : Integer[-1];
          if (n.isNegative()) return new NativeBigInt(_0);
          var x = this;
          var y = Integer[1];
          while (true) {
            if ((b & _1) === _1) {
              y = y.times(x);
              --b;
            }
            if (b === _0) break;
            b /= _2;
            x = x.square();
          }
          return y;
        };
        BigInteger.prototype.modPow = function(exp, mod) {
          exp = parseValue(exp);
          mod = parseValue(mod);
          if (mod.isZero()) throw new Error("Cannot take modPow with modulus 0");
          var r = Integer[1], base = this.mod(mod);
          if (exp.isNegative()) {
            exp = exp.multiply(Integer[-1]);
            base = base.modInv(mod);
          }
          while (exp.isPositive()) {
            if (base.isZero()) return Integer[0];
            if (exp.isOdd()) r = r.multiply(base).mod(mod);
            exp = exp.divide(2);
            base = base.square().mod(mod);
          }
          return r;
        };
        NativeBigInt.prototype.modPow = SmallInteger.prototype.modPow = BigInteger.prototype.modPow;
        function compareAbs(a, b) {
          if (a.length !== b.length) {
            return a.length > b.length ? 1 : -1;
          }
          for (var i2 = a.length - 1; i2 >= 0; i2--) {
            if (a[i2] !== b[i2]) return a[i2] > b[i2] ? 1 : -1;
          }
          return 0;
        }
        BigInteger.prototype.compareAbs = function(v) {
          var n = parseValue(v), a = this.value, b = n.value;
          if (n.isSmall) return 1;
          return compareAbs(a, b);
        };
        SmallInteger.prototype.compareAbs = function(v) {
          var n = parseValue(v), a = Math.abs(this.value), b = n.value;
          if (n.isSmall) {
            b = Math.abs(b);
            return a === b ? 0 : a > b ? 1 : -1;
          }
          return -1;
        };
        NativeBigInt.prototype.compareAbs = function(v) {
          var a = this.value;
          var b = parseValue(v).value;
          a = a >= 0 ? a : -a;
          b = b >= 0 ? b : -b;
          return a === b ? 0 : a > b ? 1 : -1;
        };
        BigInteger.prototype.compare = function(v) {
          if (v === Infinity) {
            return -1;
          }
          if (v === -Infinity) {
            return 1;
          }
          var n = parseValue(v), a = this.value, b = n.value;
          if (this.sign !== n.sign) {
            return n.sign ? 1 : -1;
          }
          if (n.isSmall) {
            return this.sign ? -1 : 1;
          }
          return compareAbs(a, b) * (this.sign ? -1 : 1);
        };
        BigInteger.prototype.compareTo = BigInteger.prototype.compare;
        SmallInteger.prototype.compare = function(v) {
          if (v === Infinity) {
            return -1;
          }
          if (v === -Infinity) {
            return 1;
          }
          var n = parseValue(v), a = this.value, b = n.value;
          if (n.isSmall) {
            return a == b ? 0 : a > b ? 1 : -1;
          }
          if (a < 0 !== n.sign) {
            return a < 0 ? -1 : 1;
          }
          return a < 0 ? 1 : -1;
        };
        SmallInteger.prototype.compareTo = SmallInteger.prototype.compare;
        NativeBigInt.prototype.compare = function(v) {
          if (v === Infinity) {
            return -1;
          }
          if (v === -Infinity) {
            return 1;
          }
          var a = this.value;
          var b = parseValue(v).value;
          return a === b ? 0 : a > b ? 1 : -1;
        };
        NativeBigInt.prototype.compareTo = NativeBigInt.prototype.compare;
        BigInteger.prototype.equals = function(v) {
          return this.compare(v) === 0;
        };
        NativeBigInt.prototype.eq = NativeBigInt.prototype.equals = SmallInteger.prototype.eq = SmallInteger.prototype.equals = BigInteger.prototype.eq = BigInteger.prototype.equals;
        BigInteger.prototype.notEquals = function(v) {
          return this.compare(v) !== 0;
        };
        NativeBigInt.prototype.neq = NativeBigInt.prototype.notEquals = SmallInteger.prototype.neq = SmallInteger.prototype.notEquals = BigInteger.prototype.neq = BigInteger.prototype.notEquals;
        BigInteger.prototype.greater = function(v) {
          return this.compare(v) > 0;
        };
        NativeBigInt.prototype.gt = NativeBigInt.prototype.greater = SmallInteger.prototype.gt = SmallInteger.prototype.greater = BigInteger.prototype.gt = BigInteger.prototype.greater;
        BigInteger.prototype.lesser = function(v) {
          return this.compare(v) < 0;
        };
        NativeBigInt.prototype.lt = NativeBigInt.prototype.lesser = SmallInteger.prototype.lt = SmallInteger.prototype.lesser = BigInteger.prototype.lt = BigInteger.prototype.lesser;
        BigInteger.prototype.greaterOrEquals = function(v) {
          return this.compare(v) >= 0;
        };
        NativeBigInt.prototype.geq = NativeBigInt.prototype.greaterOrEquals = SmallInteger.prototype.geq = SmallInteger.prototype.greaterOrEquals = BigInteger.prototype.geq = BigInteger.prototype.greaterOrEquals;
        BigInteger.prototype.lesserOrEquals = function(v) {
          return this.compare(v) <= 0;
        };
        NativeBigInt.prototype.leq = NativeBigInt.prototype.lesserOrEquals = SmallInteger.prototype.leq = SmallInteger.prototype.lesserOrEquals = BigInteger.prototype.leq = BigInteger.prototype.lesserOrEquals;
        BigInteger.prototype.isEven = function() {
          return (this.value[0] & 1) === 0;
        };
        SmallInteger.prototype.isEven = function() {
          return (this.value & 1) === 0;
        };
        NativeBigInt.prototype.isEven = function() {
          return (this.value & BigInt(1)) === BigInt(0);
        };
        BigInteger.prototype.isOdd = function() {
          return (this.value[0] & 1) === 1;
        };
        SmallInteger.prototype.isOdd = function() {
          return (this.value & 1) === 1;
        };
        NativeBigInt.prototype.isOdd = function() {
          return (this.value & BigInt(1)) === BigInt(1);
        };
        BigInteger.prototype.isPositive = function() {
          return !this.sign;
        };
        SmallInteger.prototype.isPositive = function() {
          return this.value > 0;
        };
        NativeBigInt.prototype.isPositive = SmallInteger.prototype.isPositive;
        BigInteger.prototype.isNegative = function() {
          return this.sign;
        };
        SmallInteger.prototype.isNegative = function() {
          return this.value < 0;
        };
        NativeBigInt.prototype.isNegative = SmallInteger.prototype.isNegative;
        BigInteger.prototype.isUnit = function() {
          return false;
        };
        SmallInteger.prototype.isUnit = function() {
          return Math.abs(this.value) === 1;
        };
        NativeBigInt.prototype.isUnit = function() {
          return this.abs().value === BigInt(1);
        };
        BigInteger.prototype.isZero = function() {
          return false;
        };
        SmallInteger.prototype.isZero = function() {
          return this.value === 0;
        };
        NativeBigInt.prototype.isZero = function() {
          return this.value === BigInt(0);
        };
        BigInteger.prototype.isDivisibleBy = function(v) {
          var n = parseValue(v);
          if (n.isZero()) return false;
          if (n.isUnit()) return true;
          if (n.compareAbs(2) === 0) return this.isEven();
          return this.mod(n).isZero();
        };
        NativeBigInt.prototype.isDivisibleBy = SmallInteger.prototype.isDivisibleBy = BigInteger.prototype.isDivisibleBy;
        function isBasicPrime(v) {
          var n = v.abs();
          if (n.isUnit()) return false;
          if (n.equals(2) || n.equals(3) || n.equals(5)) return true;
          if (n.isEven() || n.isDivisibleBy(3) || n.isDivisibleBy(5)) return false;
          if (n.lesser(49)) return true;
        }
        function millerRabinTest(n, a) {
          var nPrev = n.prev(), b = nPrev, r = 0, d, t, i2, x;
          while (b.isEven()) b = b.divide(2), r++;
          next: for (i2 = 0; i2 < a.length; i2++) {
            if (n.lesser(a[i2])) continue;
            x = bigInt(a[i2]).modPow(b, n);
            if (x.isUnit() || x.equals(nPrev)) continue;
            for (d = r - 1; d != 0; d--) {
              x = x.square().mod(n);
              if (x.isUnit()) return false;
              if (x.equals(nPrev)) continue next;
            }
            return false;
          }
          return true;
        }
        BigInteger.prototype.isPrime = function(strict) {
          var isPrime = isBasicPrime(this);
          if (isPrime !== undefined2) return isPrime;
          var n = this.abs();
          var bits = n.bitLength();
          if (bits <= 64)
            return millerRabinTest(n, [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]);
          var logN = Math.log(2) * bits.toJSNumber();
          var t = Math.ceil(strict === true ? 2 * Math.pow(logN, 2) : logN);
          for (var a = [], i2 = 0; i2 < t; i2++) {
            a.push(bigInt(i2 + 2));
          }
          return millerRabinTest(n, a);
        };
        NativeBigInt.prototype.isPrime = SmallInteger.prototype.isPrime = BigInteger.prototype.isPrime;
        BigInteger.prototype.isProbablePrime = function(iterations, rng) {
          var isPrime = isBasicPrime(this);
          if (isPrime !== undefined2) return isPrime;
          var n = this.abs();
          var t = iterations === undefined2 ? 5 : iterations;
          for (var a = [], i2 = 0; i2 < t; i2++) {
            a.push(bigInt.randBetween(2, n.minus(2), rng));
          }
          return millerRabinTest(n, a);
        };
        NativeBigInt.prototype.isProbablePrime = SmallInteger.prototype.isProbablePrime = BigInteger.prototype.isProbablePrime;
        BigInteger.prototype.modInv = function(n) {
          var t = bigInt.zero, newT = bigInt.one, r = parseValue(n), newR = this.abs(), q, lastT, lastR;
          while (!newR.isZero()) {
            q = r.divide(newR);
            lastT = t;
            lastR = r;
            t = newT;
            r = newR;
            newT = lastT.subtract(q.multiply(newT));
            newR = lastR.subtract(q.multiply(newR));
          }
          if (!r.isUnit()) throw new Error(this.toString() + " and " + n.toString() + " are not co-prime");
          if (t.compare(0) === -1) {
            t = t.add(n);
          }
          if (this.isNegative()) {
            return t.negate();
          }
          return t;
        };
        NativeBigInt.prototype.modInv = SmallInteger.prototype.modInv = BigInteger.prototype.modInv;
        BigInteger.prototype.next = function() {
          var value = this.value;
          if (this.sign) {
            return subtractSmall(value, 1, this.sign);
          }
          return new BigInteger(addSmall(value, 1), this.sign);
        };
        SmallInteger.prototype.next = function() {
          var value = this.value;
          if (value + 1 < MAX_INT) return new SmallInteger(value + 1);
          return new BigInteger(MAX_INT_ARR, false);
        };
        NativeBigInt.prototype.next = function() {
          return new NativeBigInt(this.value + BigInt(1));
        };
        BigInteger.prototype.prev = function() {
          var value = this.value;
          if (this.sign) {
            return new BigInteger(addSmall(value, 1), true);
          }
          return subtractSmall(value, 1, this.sign);
        };
        SmallInteger.prototype.prev = function() {
          var value = this.value;
          if (value - 1 > -MAX_INT) return new SmallInteger(value - 1);
          return new BigInteger(MAX_INT_ARR, true);
        };
        NativeBigInt.prototype.prev = function() {
          return new NativeBigInt(this.value - BigInt(1));
        };
        var powersOfTwo = [1];
        while (2 * powersOfTwo[powersOfTwo.length - 1] <= BASE) powersOfTwo.push(2 * powersOfTwo[powersOfTwo.length - 1]);
        var powers2Length = powersOfTwo.length, highestPower2 = powersOfTwo[powers2Length - 1];
        function shift_isSmall(n) {
          return Math.abs(n) <= BASE;
        }
        BigInteger.prototype.shiftLeft = function(v) {
          var n = parseValue(v).toJSNumber();
          if (!shift_isSmall(n)) {
            throw new Error(String(n) + " is too large for shifting.");
          }
          if (n < 0) return this.shiftRight(-n);
          var result = this;
          if (result.isZero()) return result;
          while (n >= powers2Length) {
            result = result.multiply(highestPower2);
            n -= powers2Length - 1;
          }
          return result.multiply(powersOfTwo[n]);
        };
        NativeBigInt.prototype.shiftLeft = SmallInteger.prototype.shiftLeft = BigInteger.prototype.shiftLeft;
        BigInteger.prototype.shiftRight = function(v) {
          var remQuo;
          var n = parseValue(v).toJSNumber();
          if (!shift_isSmall(n)) {
            throw new Error(String(n) + " is too large for shifting.");
          }
          if (n < 0) return this.shiftLeft(-n);
          var result = this;
          while (n >= powers2Length) {
            if (result.isZero() || result.isNegative() && result.isUnit()) return result;
            remQuo = divModAny(result, highestPower2);
            result = remQuo[1].isNegative() ? remQuo[0].prev() : remQuo[0];
            n -= powers2Length - 1;
          }
          remQuo = divModAny(result, powersOfTwo[n]);
          return remQuo[1].isNegative() ? remQuo[0].prev() : remQuo[0];
        };
        NativeBigInt.prototype.shiftRight = SmallInteger.prototype.shiftRight = BigInteger.prototype.shiftRight;
        function bitwise(x, y, fn) {
          y = parseValue(y);
          var xSign = x.isNegative(), ySign = y.isNegative();
          var xRem = xSign ? x.not() : x, yRem = ySign ? y.not() : y;
          var xDigit = 0, yDigit = 0;
          var xDivMod = null, yDivMod = null;
          var result = [];
          while (!xRem.isZero() || !yRem.isZero()) {
            xDivMod = divModAny(xRem, highestPower2);
            xDigit = xDivMod[1].toJSNumber();
            if (xSign) {
              xDigit = highestPower2 - 1 - xDigit;
            }
            yDivMod = divModAny(yRem, highestPower2);
            yDigit = yDivMod[1].toJSNumber();
            if (ySign) {
              yDigit = highestPower2 - 1 - yDigit;
            }
            xRem = xDivMod[0];
            yRem = yDivMod[0];
            result.push(fn(xDigit, yDigit));
          }
          var sum = fn(xSign ? 1 : 0, ySign ? 1 : 0) !== 0 ? bigInt(-1) : bigInt(0);
          for (var i2 = result.length - 1; i2 >= 0; i2 -= 1) {
            sum = sum.multiply(highestPower2).add(bigInt(result[i2]));
          }
          return sum;
        }
        BigInteger.prototype.not = function() {
          return this.negate().prev();
        };
        NativeBigInt.prototype.not = SmallInteger.prototype.not = BigInteger.prototype.not;
        BigInteger.prototype.and = function(n) {
          return bitwise(this, n, function(a, b) {
            return a & b;
          });
        };
        NativeBigInt.prototype.and = SmallInteger.prototype.and = BigInteger.prototype.and;
        BigInteger.prototype.or = function(n) {
          return bitwise(this, n, function(a, b) {
            return a | b;
          });
        };
        NativeBigInt.prototype.or = SmallInteger.prototype.or = BigInteger.prototype.or;
        BigInteger.prototype.xor = function(n) {
          return bitwise(this, n, function(a, b) {
            return a ^ b;
          });
        };
        NativeBigInt.prototype.xor = SmallInteger.prototype.xor = BigInteger.prototype.xor;
        var LOBMASK_I = 1 << 30, LOBMASK_BI = (BASE & -BASE) * (BASE & -BASE) | LOBMASK_I;
        function roughLOB(n) {
          var v = n.value, x = typeof v === "number" ? v | LOBMASK_I : typeof v === "bigint" ? v | BigInt(LOBMASK_I) : v[0] + v[1] * BASE | LOBMASK_BI;
          return x & -x;
        }
        function integerLogarithm(value, base) {
          if (base.compareTo(value) <= 0) {
            var tmp = integerLogarithm(value, base.square(base));
            var p = tmp.p;
            var e = tmp.e;
            var t = p.multiply(base);
            return t.compareTo(value) <= 0 ? { p: t, e: e * 2 + 1 } : { p, e: e * 2 };
          }
          return { p: bigInt(1), e: 0 };
        }
        BigInteger.prototype.bitLength = function() {
          var n = this;
          if (n.compareTo(bigInt(0)) < 0) {
            n = n.negate().subtract(bigInt(1));
          }
          if (n.compareTo(bigInt(0)) === 0) {
            return bigInt(0);
          }
          return bigInt(integerLogarithm(n, bigInt(2)).e).add(bigInt(1));
        };
        NativeBigInt.prototype.bitLength = SmallInteger.prototype.bitLength = BigInteger.prototype.bitLength;
        function max(a, b) {
          a = parseValue(a);
          b = parseValue(b);
          return a.greater(b) ? a : b;
        }
        function min(a, b) {
          a = parseValue(a);
          b = parseValue(b);
          return a.lesser(b) ? a : b;
        }
        function gcd(a, b) {
          a = parseValue(a).abs();
          b = parseValue(b).abs();
          if (a.equals(b)) return a;
          if (a.isZero()) return b;
          if (b.isZero()) return a;
          var c = Integer[1], d, t;
          while (a.isEven() && b.isEven()) {
            d = min(roughLOB(a), roughLOB(b));
            a = a.divide(d);
            b = b.divide(d);
            c = c.multiply(d);
          }
          while (a.isEven()) {
            a = a.divide(roughLOB(a));
          }
          do {
            while (b.isEven()) {
              b = b.divide(roughLOB(b));
            }
            if (a.greater(b)) {
              t = b;
              b = a;
              a = t;
            }
            b = b.subtract(a);
          } while (!b.isZero());
          return c.isUnit() ? a : a.multiply(c);
        }
        function lcm(a, b) {
          a = parseValue(a).abs();
          b = parseValue(b).abs();
          return a.divide(gcd(a, b)).multiply(b);
        }
        function randBetween(a, b, rng) {
          a = parseValue(a);
          b = parseValue(b);
          var usedRNG = rng || Math.random;
          var low = min(a, b), high = max(a, b);
          var range = high.subtract(low).add(1);
          if (range.isSmall) return low.add(Math.floor(usedRNG() * range));
          var digits = toBase(range, BASE).value;
          var result = [], restricted = true;
          for (var i2 = 0; i2 < digits.length; i2++) {
            var top = restricted ? digits[i2] + (i2 + 1 < digits.length ? digits[i2 + 1] / BASE : 0) : BASE;
            var digit = truncate(usedRNG() * top);
            result.push(digit);
            if (digit < digits[i2]) restricted = false;
          }
          return low.add(Integer.fromArray(result, BASE, false));
        }
        var parseBase = function(text, base, alphabet, caseSensitive) {
          alphabet = alphabet || DEFAULT_ALPHABET;
          text = String(text);
          if (!caseSensitive) {
            text = text.toLowerCase();
            alphabet = alphabet.toLowerCase();
          }
          var length = text.length;
          var i2;
          var absBase = Math.abs(base);
          var alphabetValues = {};
          for (i2 = 0; i2 < alphabet.length; i2++) {
            alphabetValues[alphabet[i2]] = i2;
          }
          for (i2 = 0; i2 < length; i2++) {
            var c = text[i2];
            if (c === "-") continue;
            if (c in alphabetValues) {
              if (alphabetValues[c] >= absBase) {
                if (c === "1" && absBase === 1) continue;
                throw new Error(c + " is not a valid digit in base " + base + ".");
              }
            }
          }
          base = parseValue(base);
          var digits = [];
          var isNegative = text[0] === "-";
          for (i2 = isNegative ? 1 : 0; i2 < text.length; i2++) {
            var c = text[i2];
            if (c in alphabetValues) digits.push(parseValue(alphabetValues[c]));
            else if (c === "<") {
              var start = i2;
              do {
                i2++;
              } while (text[i2] !== ">" && i2 < text.length);
              digits.push(parseValue(text.slice(start + 1, i2)));
            } else throw new Error(c + " is not a valid character");
          }
          return parseBaseFromArray(digits, base, isNegative);
        };
        function parseBaseFromArray(digits, base, isNegative) {
          var val = Integer[0], pow = Integer[1], i2;
          for (i2 = digits.length - 1; i2 >= 0; i2--) {
            val = val.add(digits[i2].times(pow));
            pow = pow.times(base);
          }
          return isNegative ? val.negate() : val;
        }
        function stringify(digit, alphabet) {
          alphabet = alphabet || DEFAULT_ALPHABET;
          if (digit < alphabet.length) {
            return alphabet[digit];
          }
          return "<" + digit + ">";
        }
        function toBase(n, base) {
          base = bigInt(base);
          if (base.isZero()) {
            if (n.isZero()) return { value: [0], isNegative: false };
            throw new Error("Cannot convert nonzero numbers to base 0.");
          }
          if (base.equals(-1)) {
            if (n.isZero()) return { value: [0], isNegative: false };
            if (n.isNegative())
              return {
                value: [].concat.apply(
                  [],
                  Array.apply(null, Array(-n.toJSNumber())).map(Array.prototype.valueOf, [1, 0])
                ),
                isNegative: false
              };
            var arr = Array.apply(null, Array(n.toJSNumber() - 1)).map(Array.prototype.valueOf, [0, 1]);
            arr.unshift([1]);
            return {
              value: [].concat.apply([], arr),
              isNegative: false
            };
          }
          var neg = false;
          if (n.isNegative() && base.isPositive()) {
            neg = true;
            n = n.abs();
          }
          if (base.isUnit()) {
            if (n.isZero()) return { value: [0], isNegative: false };
            return {
              value: Array.apply(null, Array(n.toJSNumber())).map(Number.prototype.valueOf, 1),
              isNegative: neg
            };
          }
          var out = [];
          var left = n, divmod;
          while (left.isNegative() || left.compareAbs(base) >= 0) {
            divmod = left.divmod(base);
            left = divmod.quotient;
            var digit = divmod.remainder;
            if (digit.isNegative()) {
              digit = base.minus(digit).abs();
              left = left.next();
            }
            out.push(digit.toJSNumber());
          }
          out.push(left.toJSNumber());
          return { value: out.reverse(), isNegative: neg };
        }
        function toBaseString(n, base, alphabet) {
          var arr = toBase(n, base);
          return (arr.isNegative ? "-" : "") + arr.value.map(function(x) {
            return stringify(x, alphabet);
          }).join("");
        }
        BigInteger.prototype.toArray = function(radix) {
          return toBase(this, radix);
        };
        SmallInteger.prototype.toArray = function(radix) {
          return toBase(this, radix);
        };
        NativeBigInt.prototype.toArray = function(radix) {
          return toBase(this, radix);
        };
        BigInteger.prototype.toString = function(radix, alphabet) {
          if (radix === undefined2) radix = 10;
          if (radix !== 10 || alphabet) return toBaseString(this, radix, alphabet);
          var v = this.value, l = v.length, str = String(v[--l]), zeros = "0000000", digit;
          while (--l >= 0) {
            digit = String(v[l]);
            str += zeros.slice(digit.length) + digit;
          }
          var sign = this.sign ? "-" : "";
          return sign + str;
        };
        SmallInteger.prototype.toString = function(radix, alphabet) {
          if (radix === undefined2) radix = 10;
          if (radix != 10 || alphabet) return toBaseString(this, radix, alphabet);
          return String(this.value);
        };
        NativeBigInt.prototype.toString = SmallInteger.prototype.toString;
        NativeBigInt.prototype.toJSON = BigInteger.prototype.toJSON = SmallInteger.prototype.toJSON = function() {
          return this.toString();
        };
        BigInteger.prototype.valueOf = function() {
          return parseInt(this.toString(), 10);
        };
        BigInteger.prototype.toJSNumber = BigInteger.prototype.valueOf;
        SmallInteger.prototype.valueOf = function() {
          return this.value;
        };
        SmallInteger.prototype.toJSNumber = SmallInteger.prototype.valueOf;
        NativeBigInt.prototype.valueOf = NativeBigInt.prototype.toJSNumber = function() {
          return parseInt(this.toString(), 10);
        };
        function parseStringValue(v) {
          if (isPrecise(+v)) {
            var x = +v;
            if (x === truncate(x))
              return supportsNativeBigInt ? new NativeBigInt(BigInt(x)) : new SmallInteger(x);
            throw new Error("Invalid integer: " + v);
          }
          var sign = v[0] === "-";
          if (sign) v = v.slice(1);
          var split = v.split(/e/i);
          if (split.length > 2) throw new Error("Invalid integer: " + split.join("e"));
          if (split.length === 2) {
            var exp = split[1];
            if (exp[0] === "+") exp = exp.slice(1);
            exp = +exp;
            if (exp !== truncate(exp) || !isPrecise(exp)) throw new Error("Invalid integer: " + exp + " is not a valid exponent.");
            var text = split[0];
            var decimalPlace = text.indexOf(".");
            if (decimalPlace >= 0) {
              exp -= text.length - decimalPlace - 1;
              text = text.slice(0, decimalPlace) + text.slice(decimalPlace + 1);
            }
            if (exp < 0) throw new Error("Cannot include negative exponent part for integers");
            text += new Array(exp + 1).join("0");
            v = text;
          }
          var isValid = /^([0-9][0-9]*)$/.test(v);
          if (!isValid) throw new Error("Invalid integer: " + v);
          if (supportsNativeBigInt) {
            return new NativeBigInt(BigInt(sign ? "-" + v : v));
          }
          var r = [], max2 = v.length, l = LOG_BASE, min2 = max2 - l;
          while (max2 > 0) {
            r.push(+v.slice(min2, max2));
            min2 -= l;
            if (min2 < 0) min2 = 0;
            max2 -= l;
          }
          trim(r);
          return new BigInteger(r, sign);
        }
        function parseNumberValue(v) {
          if (supportsNativeBigInt) {
            return new NativeBigInt(BigInt(v));
          }
          if (isPrecise(v)) {
            if (v !== truncate(v)) throw new Error(v + " is not an integer.");
            return new SmallInteger(v);
          }
          return parseStringValue(v.toString());
        }
        function parseValue(v) {
          if (typeof v === "number") {
            return parseNumberValue(v);
          }
          if (typeof v === "string") {
            return parseStringValue(v);
          }
          if (typeof v === "bigint") {
            return new NativeBigInt(v);
          }
          return v;
        }
        for (var i = 0; i < 1e3; i++) {
          Integer[i] = parseValue(i);
          if (i > 0) Integer[-i] = parseValue(-i);
        }
        Integer.one = Integer[1];
        Integer.zero = Integer[0];
        Integer.minusOne = Integer[-1];
        Integer.max = max;
        Integer.min = min;
        Integer.gcd = gcd;
        Integer.lcm = lcm;
        Integer.isInstance = function(x) {
          return x instanceof BigInteger || x instanceof SmallInteger || x instanceof NativeBigInt;
        };
        Integer.randBetween = randBetween;
        Integer.fromArray = function(digits, base, isNegative) {
          return parseBaseFromArray(digits.map(parseValue), parseValue(base || 10), isNegative);
        };
        return Integer;
      })();
      if (typeof module !== "undefined" && module.hasOwnProperty("exports")) {
        module.exports = bigInt;
      }
      if (typeof define === "function" && define.amd) {
        define(function() {
          return bigInt;
        });
      }
    }
  });

  // node_modules/3vl/dist/index.js
  var require_dist = __commonJS({
    "node_modules/3vl/dist/index.js"(exports) {
      "use strict";
      var __classPrivateFieldSet = exports && exports.__classPrivateFieldSet || function(receiver, state, value, kind, f) {
        if (kind === "m") throw new TypeError("Private method is not writable");
        if (kind === "a" && !f) throw new TypeError("Private accessor was defined without a setter");
        if (typeof state === "function" ? receiver !== state || !f : !state.has(receiver)) throw new TypeError("Cannot write private member to an object whose class did not declare it");
        return kind === "a" ? f.call(receiver, value) : f ? f.value = value : state.set(receiver, value), value;
      };
      var __classPrivateFieldGet = exports && exports.__classPrivateFieldGet || function(receiver, state, kind, f) {
        if (kind === "a" && !f) throw new TypeError("Private accessor was defined without a getter");
        if (typeof state === "function" ? receiver !== state || !f : !state.has(receiver)) throw new TypeError("Cannot read private member from an object whose class did not declare it");
        return kind === "m" ? f : kind === "a" ? f.call(receiver) : f ? f.value : state.get(receiver);
      };
      var _Display3vlWithRegex_regex;
      Object.defineProperty(exports, "__esModule", { value: true });
      exports.Display3vl = exports.Display3vlOct = exports.Display3vlBin = exports.Display3vlHex = exports.Display3vlWithRegex = exports.Mem3vl = exports.Vector3vl = exports.Error3vl = void 0;
      function zip(f, a, b) {
        return a.map((x, i) => f(x, b[i]));
      }
      function zip4(f, a, b, c, d) {
        return a.map((x, i) => f(x, b[i], c[i], d[i]));
      }
      function bitfold(f, a, lastmask, neutral) {
        if (a.length == 0)
          return neutral == 1 ? 1 : 0;
        let acc = a[a.length - 1];
        if (neutral == 1)
          acc |= ~lastmask;
        else
          acc &= lastmask;
        for (let i = 0; i < a.length - 1; i++)
          acc = f(acc, a[i]);
        acc = f(acc, acc >>> 16);
        acc = f(acc, acc >>> 8);
        acc = f(acc, acc >>> 4);
        acc = f(acc, acc >>> 2);
        acc = f(acc, acc >>> 1);
        return acc & 1;
      }
      function wordnum(n) {
        return n >> 5;
      }
      function bitnum(n) {
        return n & 31;
      }
      function fillRest(m, k, words, avec, bvec) {
        const last_x = m > 0 && !(avec[k] & 1 << m - 1) && bvec[k] & 1 << m - 1;
        if (last_x && bitnum(m))
          bvec[k] |= -1 << m;
        if (last_x && k + 1 < words) {
          bvec.fill(-1, k + 1);
        }
      }
      function makeMap(bits, depth) {
        const ret = {};
        function g(what, val) {
          ret[what] = val;
          if (what.length * bits >= depth)
            return;
          for (let i = 0; i < 1 << bits; i += 1)
            g(what + i.toString(1 << bits), val << bits | i | i << 16);
          g(what + "x", val << bits | (1 << bits) - 1);
        }
        g("", 0);
        Object.seal(ret);
        return ret;
      }
      var fromBinMap = makeMap(1, 8);
      var fromOctMap = makeMap(3, 3);
      var fromHexMap = makeMap(4, 8);
      function toHexInternal(start, bits, avec, bvec) {
        const out = [];
        let bit = 0, k = start;
        while (bit < bits) {
          const a = "00000000" + avec[k].toString(16);
          const x = avec[k] ^ bvec[k];
          k++;
          for (let b = 0; b < 8 && bit < bits; b++, bit += 4) {
            if (x & 15 << 4 * b)
              out.push("x");
            else
              out.push(a[a.length - 1 - b]);
          }
        }
        return out.reverse().join("");
      }
      function toBinInternal(start, bits, avec, bvec) {
        const out = [];
        let bit = 0, k = start;
        while (bit < bits) {
          const a = "00000000000000000000000000000000" + avec[k].toString(2);
          const x = avec[k] ^ bvec[k];
          k++;
          for (let b = 0; b < 32 && bit < bits; b++, bit++) {
            if (x & 1 << b)
              out.push("x");
            else
              out.push(a[a.length - 1 - b]);
          }
        }
        return out.reverse().join("");
      }
      function fromHexInternal(data, start, nbits, avec, bvec) {
        const skip = 4;
        const words = nbits + 31 >>> 5;
        let m = 0, k = -1 + start;
        for (let i = data.length; i > 0; ) {
          const frag = data.slice(Math.max(0, i - 2), i);
          i -= frag.length;
          const v = fromHexMap[frag];
          if (bitnum(m) == 0)
            k++;
          const mask = (1 << skip * frag.length) - 1;
          avec[k] |= (v >>> 16 & mask) << m;
          bvec[k] |= (v & mask) << m;
          m += skip * frag.length;
        }
        if (m < nbits)
          fillRest(m, k, words, avec, bvec);
      }
      function fromBinInternal(data, start, nbits, avec, bvec) {
        const skip = 1;
        const words = nbits + 31 >>> 5;
        let m = 0, k = -1 + start;
        for (let i = data.length; i > 0; ) {
          const frag = data.slice(Math.max(0, i - 8), i);
          i -= frag.length;
          const v = fromBinMap[frag];
          if (bitnum(m) == 0)
            k++;
          const mask = (1 << skip * frag.length) - 1;
          avec[k] |= (v >>> 16 & mask) << m;
          bvec[k] |= (v & mask) << m;
          m += skip * frag.length;
        }
        if (m < nbits)
          fillRest(m, k, words, avec, bvec);
      }
      var Error3vl = class _Error3vl extends Error {
        constructor(s) {
          super(s);
          Object.setPrototypeOf(this, _Error3vl.prototype);
        }
      };
      exports.Error3vl = Error3vl;
      function assert(c, s) {
        if (!c)
          throw new Error3vl("Assertion failed: " + s);
      }
      var Vector3vl = class _Vector3vl {
        /**
         * Private constructor for three-value logic vectors.
         *
         * **Only for internal use.**
         *
         * @param bits Number of bits in the vector.
         * @param avec Bit vector A.
         * @param bvec Bit vector B.
         */
        constructor(bits, avec, bvec) {
          this._bits = bits;
          this._avec = avec;
          this._bvec = bvec;
        }
        /**
         * Construct a vector with a constant value at each position.
         *
         * @param bits Number of bits in the vector.
         * @param init Initializer. Recognized values:
         * * false, -1, '0' for logical 0,
         * * 0, 'x' for undefined value,
         * * true, 1, '1' for logical 1.
         */
        static make(bits, init) {
          bits = bits | 0;
          let iva, ivb;
          switch (init) {
            case true:
            case "1":
            case 1:
              iva = ivb = ~0;
              break;
            case false:
            case "0":
            case -1:
            case void 0:
              iva = ivb = 0;
              break;
            case "x":
            case 0:
              iva = 0;
              ivb = ~0;
              break;
            default:
              assert(false, "Vector3vl.make() called with invalid initializer");
          }
          const words = (bits + 31) / 32 | 0;
          return new _Vector3vl(bits, new Uint32Array(words).fill(iva), new Uint32Array(words).fill(ivb));
        }
        /**
         * Construct a vector containing only zeros.
         *
         * @param bits Number of bits in the vector.
         */
        static zeros(bits) {
          return _Vector3vl.make(bits, -1);
        }
        /**
         * Construct a vector containing only ones.
         *
         * @param bits Number of bits in the vector.
         */
        static ones(bits) {
          return _Vector3vl.make(bits, 1);
        }
        /**
         * Construct a vector containing only undefined values.
         *
         * @param bits Number of bits in the vector.
         */
        static xes(bits) {
          return _Vector3vl.make(bits, 0);
        }
        /**
         * Construct a vector containing Boolean value _b_.
         *
         * @param b Boolean value for the vector.
         * @param bits Number of bits in the vector.
         */
        static fromBool(b, bits = 1) {
          return _Vector3vl.make(bits, b ? 1 : -1);
        }
        /**
         * Concatenate vectors into a single big vector.
         *
         * @param vs Vectors to concatenate.
         *           Arguments are ordered least significant bit first.
         */
        static concat(...vs) {
          const sumbits = vs.reduce((y, x) => x.bits + y, 0);
          const words = sumbits + 31 >>> 5;
          let bits = 0, idx = -1, avec = new Uint32Array(words), bvec = new Uint32Array(words);
          for (const v of vs) {
            v.normalize();
            if (bitnum(bits) == 0) {
              avec.set(v._avec, idx + 1);
              bvec.set(v._bvec, idx + 1);
              bits += v._bits;
              idx += v._bits + 31 >>> 5;
            } else {
              for (const k in v._avec) {
                avec[idx] |= v._avec[k] << bits;
                bvec[idx] |= v._bvec[k] << bits;
                idx++;
                if (idx == words)
                  break;
                avec[idx] = v._avec[k] >>> -bits;
                bvec[idx] = v._bvec[k] >>> -bits;
              }
              bits += v._bits;
              if (idx + 1 > bits + 31 >>> 5) {
                idx--;
              }
            }
          }
          return new _Vector3vl(bits, avec, bvec);
        }
        /**
         * Construct a vector from an iterable.
         *
         * This function calls [[fromIteratorAnySkip]] or [[fromIteratorPow2]].
         *
         * @param iter Iterable returning initialization values, least to most
         *             significant. First _skip_ bits go to vector B, next
         *             _skip_ bits go to vector A.
         * @param skip Number of bits in a single iterator step. 1 to 16.
         * @param nbits Number of bits in the vector.
         */
        static fromIterator(iter, skip, nbits) {
          if ((skip & skip - 1) == 0)
            return _Vector3vl.fromIteratorPow2(iter, skip, nbits);
          else
            return _Vector3vl.fromIteratorAnySkip(iter, skip, nbits);
        }
        /**
         * Construct a vector from an iterable.
         *
         * This function is more generic, but slower, than [[fromIteratorPow2]].
         *
         * @param iter Iterable returning initialization values, least to most
         *             significant. First _skip_ bits go to vector B, next
         *             _skip_ bits go to vector A.
         * @param skip Number of bits in a single iterator step. 1 to 16.
         * @param nbits Number of bits in the vector.
         */
        static fromIteratorAnySkip(iter, skip, nbits) {
          const words = nbits + 31 >>> 5;
          let m = 0, k = -1, avec = new Uint32Array(words), bvec = new Uint32Array(words);
          const mask = (1 << skip) - 1;
          for (const v of iter) {
            if (bitnum(m) == 0)
              k++;
            avec[k] |= (v >>> skip & mask) << m;
            bvec[k] |= (v & mask) << m;
            if (mask << m >>> m != mask) {
              k++;
              avec[k] = (v >>> skip & mask) >>> -m;
              bvec[k] = (v & mask) >>> -m;
            }
            m += skip;
          }
          if (m < nbits)
            fillRest(m, k, words, avec, bvec);
          return new _Vector3vl(nbits, avec, bvec);
        }
        /**
         * Construct a vector from an iterable.
         *
         * This function is limited to power of 2 _skip_ values.
         * For generic version, see [[fromIteratorAnySkip]].
         *
         * @param iter Iterable returning initialization values, least to most
         *             significant. First _skip_ bits go to vector B, next
         *             _skip_ bits go to vector A.
         * @param skip Number of bits in a single iterator step.
         *             Limited to powers of 2: 1, 2, 4, 8, 16.
         * @param nbits Number of bits in the vector.
         */
        static fromIteratorPow2(iter, skip, nbits) {
          const words = nbits + 31 >>> 5;
          let m = 0, k = -1, avec = new Uint32Array(words), bvec = new Uint32Array(words);
          const mask = (1 << skip) - 1;
          for (const v of iter) {
            if (bitnum(m) == 0)
              k++;
            avec[k] |= (v >>> skip & mask) << m;
            bvec[k] |= (v & mask) << m;
            m += skip;
          }
          if (m < nbits)
            fillRest(m, k, words, avec, bvec);
          return new _Vector3vl(nbits, avec, bvec);
        }
        /**
         * Construct a vector from an array of numbers.
         *
         * The following interpretation is used:
         * * -1 for logical 0,
         * * 0 for undefined value,
         * * 1 for logical 1.
         *
         * @param data Input array.
         */
        static fromArray(data) {
          const nbits = data.length;
          const skip = 1;
          const words = nbits + 31 >>> 5;
          let m = 0, k = -1, avec = new Uint32Array(words), bvec = new Uint32Array(words);
          const mask = (1 << skip) - 1;
          for (const x of data) {
            const v = x + 1 + Number(x > 0);
            if (bitnum(m) == 0)
              k++;
            avec[k] |= (v >>> skip & mask) << m;
            bvec[k] |= (v & mask) << m;
            m += skip;
          }
          if (m < nbits)
            fillRest(m, k, words, avec, bvec);
          return new _Vector3vl(nbits, avec, bvec);
        }
        /**
         * Construct a vector from a binary string.
         *
         * Three characters are accepted:
         * * '0' for logical 0,
         * * 'x' for undefined value,
         * * '1' for logical 1.
         *
         * If _nbits_ is given, _data_ is either truncated, or extended with
         * undefined values.
         *
         * @param data The binary string to be parsed.
         * @param nbits Number of bits in the vector. If omitted, the resulting
         *              vector has number of bits equal to the length of _data_.
         */
        static fromBin(data, nbits) {
          if (nbits === void 0)
            nbits = data.length;
          const words = nbits + 31 >>> 5;
          const avec = new Uint32Array(words), bvec = new Uint32Array(words);
          fromBinInternal(data, 0, nbits, avec, bvec);
          return new _Vector3vl(nbits, avec, bvec);
        }
        /**
         * Construct a vector from an octal number.
         *
         * Characters '0' to '7' and 'x' are accepted. The character 'x'
         * means three undefined bits.
         *
         * If _nbits_ is given, _data_ is either truncated, or extended with
         * undefined values.
         *
         * @param data The octal string to be parsed.
         * @param nbits Number of bits in the vector. If omitted, the resulting
         *              vector has number of bits equal to the length of _data_
         *              times three.
         */
        static fromOct(data, nbits) {
          const skip = 3;
          if (nbits === void 0)
            nbits = data.length * skip;
          const words = nbits + 31 >>> 5;
          let m = 0, k = -1, avec = new Uint32Array(words), bvec = new Uint32Array(words);
          const mask = (1 << skip) - 1;
          for (let i = data.length - 1; i >= 0; i--) {
            const v = fromOctMap[data[i]];
            if (bitnum(m) == 0)
              k++;
            avec[k] |= (v >>> 16 & mask) << m;
            bvec[k] |= (v & mask) << m;
            if (mask << m >>> m != mask) {
              k++;
              avec[k] = (v >>> 16 & mask) >>> -m;
              bvec[k] = (v & mask) >>> -m;
            }
            m += skip;
          }
          if (m < nbits)
            fillRest(m, k, words, avec, bvec);
          return new _Vector3vl(nbits, avec, bvec);
        }
        /**
         * Construct a vector from a hexadecimal number.
         *
         * Characters '0' to '9', 'a' to 'f' and 'x' are accepted. The character
         * 'x' means three undefined bits.
         *
         * If _nbits_ is given, _data_ is either truncated, or extended with
         * undefined values.
         *
         * @param data The hexadecimal string to be parsed.
         * @param nbits Number of bits in the vector. If omitted, the resulting
         *              vector has number of bits equal to the length of _data_
         *              times four.
         */
        static fromHex(data, nbits) {
          if (nbits === void 0)
            nbits = data.length * 4;
          const words = nbits + 31 >>> 5;
          const avec = new Uint32Array(words), bvec = new Uint32Array(words);
          fromHexInternal(data, 0, nbits, avec, bvec);
          return new _Vector3vl(nbits, avec, bvec);
        }
        /**
         * Construct a vector from a Verilog-like string.
         */
        static fromString(data) {
          const re = /^([0-9]*)'?(b[01x]*|o[0-7x]*|h[0-9a-fx]*|d[0-9]*)$/;
          const res = re.exec(data);
          assert(res != null, "Vector3vl.fromString() Invalid string");
          const bits = res[1].length ? Number(res[1]) : void 0;
          const num = res[2].slice(1);
          switch (res[2][0]) {
            case "b":
              return _Vector3vl.fromBin(num, bits);
            case "o":
              return _Vector3vl.fromOct(num, bits);
            case "h":
              return _Vector3vl.fromHex(num, bits);
            case "d":
              return _Vector3vl.fromNumber(BigInt(num), bits);
          }
        }
        /**
         * Construct a vector from clonable representation.
         *
         * @param data The initialization value.
         */
        static fromClonable(data) {
          return new _Vector3vl(data._bits, data._avec, data._bvec);
        }
        /**
         * Construct a vector from a number or a bigint.
         *
         * If _nbits_ bits are not enough to represent the number, it is
         * truncated. If it's larger, the number is sign-extended.
         * If it is not given, the resulting vector will have enough bits
         * to represent the number completely.
         *
         * @param data The initialization value.
         * @param nbits Number of bits in the vector.
         */
        static fromNumber(data, nbits) {
          const fbits = nbits === void 0 ? 0 : nbits;
          const bdata = BigInt(data);
          if (bdata >= BigInt(0)) {
            let b = bdata.toString(2);
            return _Vector3vl.fromBin("0".repeat(Math.max(0, fbits - b.length)) + b, nbits);
          } else {
            const c = (-bdata).toString(2).length;
            const j = bdata + (BigInt(1) << BigInt(c));
            let b = j.toString(2);
            return _Vector3vl.fromBin("1".repeat(Math.max(1, fbits - c)) + "0".repeat(c - b.length) + b, nbits);
          }
        }
        /**
         * Number of bits in the vector.
         */
        get bits() {
          return this._bits;
        }
        /**
         * Most significant bit in the vector. Returns -1, 0 or 1.
         */
        get msb() {
          return this.get(this._bits - 1);
        }
        /**
         * Least significant bit in the vector. Returns -1, 0 or 1.
         */
        get lsb() {
          return this.get(0);
        }
        /**
         * Gets _n_th value in the vector. Returns -1, 0 or 1.
         */
        get(n) {
          const bn = bitnum(n);
          const wn = wordnum(n);
          const a = this._avec[wn] >>> bn & 1;
          const b = this._bvec[wn] >>> bn & 1;
          return a + b - 1;
        }
        /**
         * Tests if the vector is all ones.
         */
        get isHigh() {
          if (this._bits == 0)
            return true;
          const lastmask = this._lastmask;
          const vechigh = (vec) => vec.slice(0, vec.length - 1).every((x) => ~x == 0) && (vec[vec.length - 1] & lastmask) == lastmask;
          return vechigh(this._avec) && vechigh(this._bvec);
        }
        /**
         * Tests if the vector is all zeros.
         */
        get isLow() {
          if (this._bits == 0)
            return true;
          const lastmask = this._lastmask;
          const veclow = (vec) => vec.slice(0, vec.length - 1).every((x) => x == 0) && (vec[vec.length - 1] & lastmask) == 0;
          return veclow(this._avec) && veclow(this._bvec);
        }
        /**
         * Tests if there is any defined bit in the vector.
         */
        get isDefined() {
          if (this._bits == 0)
            return false;
          const dvec = zip((a, b) => a ^ b, this._avec, this._bvec);
          dvec[dvec.length - 1] |= ~this._lastmask;
          return !dvec.every((x) => ~x == 0);
        }
        /**
         * Tests if every bit in the vector is defined.
         */
        get isFullyDefined() {
          if (this._bits == 0)
            return true;
          const dvec = zip((a, b) => a ^ b, this._avec, this._bvec);
          dvec[dvec.length - 1] &= this._lastmask;
          return !dvec.some((x) => Boolean(x));
        }
        /**
         * Bitwise AND of two vectors.
         *
         * The vectors need to be the same bit length.
         *
         * @param v The other vector.
         */
        and(v) {
          assert(v._bits == this._bits, "Vector3vl.and() called with vectors of different sizes");
          return new _Vector3vl(this._bits, zip((a, b) => a & b, v._avec, this._avec), zip((a, b) => a & b, v._bvec, this._bvec));
        }
        /**
         * Bitwise OR of two vectors.
         *
         * The vectors need to be the same bit length.
         *
         * @param v The other vector.
         */
        or(v) {
          assert(v._bits == this._bits, "Vector3vl.or() called with vectors of different sizes");
          return new _Vector3vl(this._bits, zip((a, b) => a | b, v._avec, this._avec), zip((a, b) => a | b, v._bvec, this._bvec));
        }
        /**
         * Bitwise XOR of two vectors.
         *
         * The vectors need to be the same bit length.
         *
         * @param v The other vector.
         */
        xor(v) {
          assert(v._bits == this._bits, "Vector3vl.xor() called with vectors of different sizes");
          return new _Vector3vl(this._bits, zip4((a1, a2, b1, b2) => (a1 | b1) & (a2 ^ b2), v._avec, v._bvec, this._avec, this._bvec), zip4((a1, a2, b1, b2) => a1 & b1 ^ (a2 | b2), v._avec, v._bvec, this._avec, this._bvec));
        }
        /**
         * Bitwise NAND of two vectors.
         *
         * The vectors need to be the same bit length.
         *
         * @param v The other vector.
         */
        nand(v) {
          assert(v._bits == this._bits, "Vector3vl.nand() called with vectors of different sizes");
          return new _Vector3vl(this._bits, zip((a, b) => ~(a & b), v._bvec, this._bvec), zip((a, b) => ~(a & b), v._avec, this._avec));
        }
        /**
         * Bitwise NOR of two vectors.
         *
         * The vectors need to be the same bit length.
         *
         * @param v The other vector.
         */
        nor(v) {
          assert(v._bits == this._bits, "Vector3vl.nor() called with vectors of different sizes");
          return new _Vector3vl(this._bits, zip((a, b) => ~(a | b), v._bvec, this._bvec), zip((a, b) => ~(a | b), v._avec, this._avec));
        }
        /**
         * Bitwise XNOR of two vectors.
         *
         * The vectors need to be the same bit length.
         *
         * @param v The other vector.
         */
        xnor(v) {
          assert(v._bits == this._bits, "Vector3vl.xnor() called with vectors of different sizes");
          return new _Vector3vl(this._bits, zip4((a1, a2, b1, b2) => ~(a1 & b1 ^ (a2 | b2)), v._avec, v._bvec, this._avec, this._bvec), zip4((a1, a2, b1, b2) => ~((a1 | b1) & (a2 ^ b2)), v._avec, v._bvec, this._avec, this._bvec));
        }
        /**
         * Bitwise NOT of a vector. */
        not() {
          return new _Vector3vl(this._bits, this._bvec.map((a) => ~a), this._avec.map((a) => ~a));
        }
        /**
         * Return a vector with 1 on locations with x, the rest with 0.
         */
        xmask() {
          const v = zip((a, b) => a ^ b, this._avec, this._bvec);
          return new _Vector3vl(this._bits, v, v);
        }
        /**
         * Reducing AND of a vector.
         *
         * ANDs all bits of the vector together, producing a single bit.
         *
         * @returns Singleton vector.
         */
        reduceAnd() {
          return new _Vector3vl(1, Uint32Array.of(bitfold((a, b) => a & b, this._avec, this._lastmask, 1)), Uint32Array.of(bitfold((a, b) => a & b, this._bvec, this._lastmask, 1)));
        }
        /**
         * Reducing OR of a vector.
         *
         * ORs all bits of the vector together, producing a single bit.
         *
         * @returns Singleton vector.
         */
        reduceOr() {
          return new _Vector3vl(1, Uint32Array.of(bitfold((a, b) => a | b, this._avec, this._lastmask, 0)), Uint32Array.of(bitfold((a, b) => a | b, this._bvec, this._lastmask, 0)));
        }
        /**
         * Reducing NAND of a vector.
         *
         * NANDs all bits of the vector together, producing a single bit.
         *
         * @returns Singleton vector.
         */
        reduceNand() {
          return new _Vector3vl(1, Uint32Array.of(~bitfold((a, b) => a & b, this._bvec, this._lastmask, 1)), Uint32Array.of(~bitfold((a, b) => a & b, this._avec, this._lastmask, 1)));
        }
        /**
         * Reducing NOR of a vector.
         *
         * NORs all bits of the vector together, producing a single bit.
         *
         * @returns Singleton vector.
         */
        reduceNor() {
          return new _Vector3vl(1, Uint32Array.of(~bitfold((a, b) => a | b, this._bvec, this._lastmask, 0)), Uint32Array.of(~bitfold((a, b) => a | b, this._avec, this._lastmask, 0)));
        }
        /**
         * Reducing XOR of a vector.
         *
         * XORs all bits of the vector together, producing a single bit.
         *
         * @returns Singleton vector.
         */
        reduceXor() {
          const xes = zip((a, b) => ~a & b, this._avec, this._bvec);
          const has_x = bitfold((a, b) => a | b, xes, this._lastmask, 0);
          const v = bitfold((a, b) => a ^ b, this._avec, this._lastmask, 0);
          return new _Vector3vl(1, Uint32Array.of(v & ~has_x), Uint32Array.of(v | has_x));
        }
        /**
         * Reducing XNOR of a vector.
         *
         * XNORs all bits of the vector together, producing a single bit.
         *
         * @return Singleton vector.
         */
        reduceXnor() {
          return this.reduceXor().not();
        }
        /**
         * Concatenates vectors, including this one, into a single vector.
         *
         * @param vs The other vectors.
         */
        concat(...vs) {
          return _Vector3vl.concat(this, ...vs);
        }
        /**
         * Return a subvector.
         *
         * Uses same conventions as the slice function for JS arrays.
         *
         * @param start Number of the first bit to include in the result.
         *              If omitted, first bit of the vector is used.
         * @param end Number of the last bit to include in the result, plus one.
         *            If omitted, last bit of the vector is used.
         */
        slice(start, end) {
          if (start === void 0)
            start = 0;
          if (end === void 0)
            end = this._bits;
          if (end > this.bits)
            end = this.bits;
          if (start > end)
            end = start;
          if (bitnum(start) == 0) {
            const avec = this._avec.slice(start >>> 5, end + 31 >>> 5);
            const bvec = this._bvec.slice(start >>> 5, end + 31 >>> 5);
            return new _Vector3vl(end - start, avec, bvec);
          } else {
            const words = end - start + 31 >>> 5;
            const avec = new Uint32Array(words), bvec = new Uint32Array(words);
            let k = 0;
            avec[k] = this._avec[start >> 5] >>> start;
            bvec[k] = this._bvec[start >> 5] >>> start;
            for (let idx = (start >> 5) + 1; idx <= end >>> 5; idx++) {
              avec[k] |= this._avec[idx] << -start;
              bvec[k] |= this._bvec[idx] << -start;
              k++;
              if (k == words)
                break;
              avec[k] = this._avec[idx] >>> start;
              bvec[k] = this._bvec[idx] >>> start;
            }
            return new _Vector3vl(end - start, avec, bvec);
          }
        }
        /**
         * Returns an iterator describing the vector.
         *
         * In each returned value, first _skip_ bits come from the vector B,
         * the next _skip_ bits come from the vector A.
         *
         * This function calls [[toIteratorAnySkip]] or [[toIteratorPow2]].
         *
         * @param skip Number of bits in a single iterator step. 1 to 16.
         */
        toIterator(skip) {
          if ((skip & skip - 1) == 0)
            return this.toIteratorPow2(skip);
          else
            return this.toIteratorAnySkip(skip);
        }
        /**
         * Returns an iterator describing the vector.
         *
         * In each returned value, first _skip_ bits come from the vector B,
         * the next _skip_ bits come from the vector A.
         *
         * @param skip Number of bits in a single iterator step. 1 to 16.
         */
        *toIteratorAnySkip(skip) {
          this.normalize();
          const sm = (1 << skip) - 1;
          let bit = 0, k = 0, m = sm, out = [];
          while (bit < this._bits) {
            let a = (this._avec[k] & m) >>> bit;
            let b = (this._bvec[k] & m) >>> bit;
            if (m >>> bit != sm && k + 1 != this._avec.length) {
              const m1 = sm >> -bit;
              a |= (this._avec[k + 1] & m1) << -bit;
              b |= (this._bvec[k + 1] & m1) << -bit;
            }
            yield a << skip | b;
            m <<= skip;
            bit += skip;
            if (m == 0) {
              k++;
              m = sm << bit;
            }
          }
        }
        /**
         * Returns an iterator describing the vector.
         *
         * In each returned value, first _skip_ bits come from the vector B,
         * the next _skip_ bits come from the vector A.
         *
         * @param skip Number of bits in a single iterator step. 1, 2, 4, 8 or 16.
         */
        *toIteratorPow2(skip) {
          this.normalize();
          const sm = (1 << skip) - 1;
          let bit = 0, k = 0, m = sm, out = [];
          while (bit < this._bits) {
            const a = (this._avec[k] & m) >>> bit;
            const b = (this._bvec[k] & m) >>> bit;
            yield a << skip | b;
            m <<= skip;
            bit += skip;
            if (m == 0) {
              k++;
              m = sm;
            }
          }
        }
        /** Returns an array representation of the vector.
         *
         * The resulting array contains values -1, 0, 1.
         */
        toArray() {
          this.normalize();
          const skip = 1;
          const sm = (1 << skip) - 1;
          let bit = 0, k = 0, m = sm, out = [];
          while (bit < this._bits) {
            const a = (this._avec[k] & m) >>> bit;
            const b = (this._bvec[k] & m) >>> bit;
            const v = a << skip | b;
            out.push(v - 1 - Number(v > 1));
            m <<= skip;
            bit += skip;
            if (m == 0) {
              k++;
              m = sm;
            }
          }
          return out;
        }
        /** Returns a binary representation of the vector.
         *
         * Three characters are used:
         * * '0' for logical 0,
         * * 'x' for undefined value,
         * * '1' for logical 1.
         */
        toBin() {
          return toBinInternal(0, this._bits, this._avec, this._bvec);
        }
        /** Returns an octal representation of the vector.
         *
         * Returned characters can be '0' to '7' and 'x'. An 'x' value is returned
         * if any of the three bits is undefined.
         */
        toOct() {
          this.normalize();
          const skip = 3;
          const sm = (1 << skip) - 1;
          let bit = 0, k = 0, m = sm, out = [];
          while (bit < this._bits) {
            let a = (this._avec[k] & m) >>> bit;
            let b = (this._bvec[k] & m) >>> bit;
            if (m >>> bit != sm && k + 1 != this._avec.length) {
              const m1 = sm >> -bit;
              a |= (this._avec[k + 1] & m1) << -bit;
              b |= (this._bvec[k + 1] & m1) << -bit;
            }
            const v = a << skip | b;
            if (7 & v & ~(v >> 3))
              out.push("x");
            else
              out.push((v >> 3).toString());
            m <<= skip;
            bit += skip;
            if (m == 0) {
              k++;
              m = sm << bit;
            }
          }
          return out.reverse().join("");
        }
        /** Returns an hexadecimal representation of the vector.
         *
         * Returned characters can be '0' to '9', 'a' to 'f' and 'x'. An 'x' value
         * is returned if any of the four bits is undefined.
         */
        toHex() {
          this.normalize();
          return toHexInternal(0, this._bits, this._avec, this._bvec);
        }
        /** Returns a string describing the vector. */
        toString() {
          return "Vector3vl " + this.toBin();
        }
        /** Returns an object which can be copied by structured clone. */
        toClonable() {
          return { _bits: this._bits, _avec: this._avec, _bvec: this._bvec };
        }
        /** Returns a number representing the vector. */
        toNumber(signed = false) {
          if (signed)
            return this.toNumberSigned();
          assert(this.isFullyDefined, "Vector3vl.toNumber() called on a not fully defined vector");
          assert(this._bits < 32, "Vector3vl.toNumber() called on a too wide vector");
          if (this._bits == 0)
            return 0;
          else
            return Number.parseInt(this.toHex(), 16);
        }
        /** Return a signed number representing the vector. */
        toNumberSigned() {
          assert(this.isFullyDefined, "Vector3vl.toNumberSigned() called on a not fully defined vector");
          assert(this._bits < 32, "Vector3vl.toNumberSigned() called on a too wide vector");
          assert(this._bits > 0, "Vector3vl.toNumberSigned() called on an empty vector");
          const sign = this.msb == 1;
          return sign ? Number.parseInt(this.toHex(), 16) - (1 << this._bits) : Number.parseInt(this.toHex(), 16);
        }
        /** Returns a BigInt representing the vector. */
        toBigInt(signed = false) {
          if (signed)
            return this.toBigIntSigned();
          assert(this.isFullyDefined, "Vector3vl.toBigInt() called on a not fully defined vector");
          if (this._bits == 0)
            return BigInt(0);
          else
            return BigInt("0x" + this.toHex());
        }
        /** Return a signed BigInt representing the vector. */
        toBigIntSigned() {
          assert(this.isFullyDefined, "Vector3vl.toBigIntSigned() called on a not fully defined vector");
          assert(this._bits > 0, "Vector3vl.toBigIntSigned() called on an empty vector");
          const sign = this.msb == 1;
          return sign ? BigInt("0x" + this.toHex()) - (BigInt(1) << BigInt(this._bits)) : BigInt("0x" + this.toHex());
        }
        /** Compares two vectors for equality. */
        eq(v) {
          if (v._bits != this._bits)
            return false;
          this.normalize();
          v.normalize();
          for (const i in this._avec) {
            if (this._avec[i] != v._avec[i])
              return false;
            if (this._bvec[i] != v._bvec[i])
              return false;
          }
          return true;
        }
        /** Normalize the vector.
         *
         * Because of the representation used, if _bits_ is not a multiple
         * of 32, some internal bits do not contribute to the vector value,
         * and for performance reasons can get arbitrary values in the course
         * of computations. This procedure clears these bits.
         * For internal use.
         */
        normalize() {
          const lastmask = this._lastmask;
          this._avec[this._avec.length - 1] &= lastmask;
          this._bvec[this._bvec.length - 1] &= lastmask;
        }
        /** Mask for unused bits.
         *
         * For internal use.
         */
        get _lastmask() {
          return ~0 >>> -this.bits;
        }
      };
      exports.Vector3vl = Vector3vl;
      Vector3vl.empty = Vector3vl.zeros(0);
      Vector3vl.one = Vector3vl.ones(1);
      Vector3vl.zero = Vector3vl.zeros(1);
      Vector3vl.x = Vector3vl.xes(1);
      var Mem3vl = class _Mem3vl {
        constructor(bits, size, val) {
          if (val === void 0)
            val = 0;
          this._bits = bits | 0;
          this._size = size | 0;
          this._wpc = (bits + 31) / 32 | 0;
          this._avec = new Uint32Array(size * this._wpc).fill(val > 0 ? ~0 : 0);
          this._bvec = new Uint32Array(size * this._wpc).fill(val >= 0 ? ~0 : 0);
          if (this._size)
            this.set(this._size - 1, this.get(this._size - 1));
        }
        static fromData(data) {
          if (data.length == 0)
            return new _Mem3vl(0, 0);
          const ret = new _Mem3vl(data[0].bits, data.length);
          for (const i in data) {
            data[i].normalize();
            assert(data[i].bits == ret._bits, "Mem3vl.fromData() called with vectors of different sizes");
            for (let j = 0; j < ret._wpc; j++) {
              const idx = Number(i) * ret._wpc + j;
              ret._avec[idx] = data[i]._avec[j];
              ret._bvec[idx] = data[i]._bvec[j];
            }
          }
          return ret;
        }
        get bits() {
          return this._bits;
        }
        get words() {
          return this._size;
        }
        get(i) {
          const idx = this._wpc * i;
          return new Vector3vl(this._bits, this._avec.slice(idx, idx + this._wpc), this._bvec.slice(idx, idx + this._wpc));
        }
        set(i, v) {
          assert(v.bits == this._bits, "Mem3vl.set() called with a vector with different bit width than the memory");
          v.normalize();
          for (let j = 0; j < this._wpc; j++) {
            this._avec[i * this._wpc + j] = v._avec[j];
            this._bvec[i * this._wpc + j] = v._bvec[j];
          }
        }
        toJSON() {
          const rep = [];
          let hexbuf = [];
          let rleval, rlecnt = 0;
          const hexflush = () => {
            if (hexbuf.length == 0)
              return;
            if (hexbuf.reduce((a, b) => a + b.length, 0) == this._bits) {
              const last = hexbuf.pop();
              if (hexbuf.length > 0)
                rep.push(hexbuf.join(""));
              rep.push(last);
            } else {
              rep.push(hexbuf.join(""));
            }
            hexbuf = [];
          };
          const rleflush = () => {
            if (rlecnt == 0)
              return;
            else if (rlecnt == 1) {
              if (rleval.length == this._bits) {
                hexflush();
                rep.push(rleval);
              } else
                hexbuf.push(rleval);
            } else {
              hexflush();
              rep.push(rlecnt);
              rep.push(rleval);
            }
            rleval = void 0;
            rlecnt = 0;
          };
          const rlepush = (v) => {
            if (rleval == v)
              rlecnt++;
            else {
              rleflush();
              rleval = v;
              rlecnt = 1;
            }
          };
          for (let i = 0; i < this._size; i++) {
            const check = () => {
              for (let j = 0; j < this._wpc; j++) {
                const xx = this._avec[i * this._wpc + j] ^ this._bvec[i * this._wpc + j];
                for (let k = 0; k < 4; k++) {
                  const m = 255 << k * 16;
                  const xm = xx & m;
                  if (xm != m || xm != 0)
                    return false;
                }
              }
              return true;
            };
            if (this._bits > 0 && check()) {
              rlepush(toHexInternal(i * this._wpc, this._bits, this._avec, this._bvec));
            } else {
              rlepush(toBinInternal(i * this._wpc, this._bits, this._avec, this._bvec));
            }
          }
          rleflush();
          hexflush();
          return rep;
        }
        static fromJSON(bits, rep) {
          const hexlen = Math.ceil(bits / 4);
          let size = 0;
          const xsize = (x) => {
            if (x.length == bits || x.length == hexlen)
              return 1;
            else
              return x.length / hexlen;
          };
          for (let i = 0; i < rep.length; i++) {
            if (typeof rep[i] === "string") {
              size += xsize(rep[i]);
            } else if (typeof rep[i] === "number") {
              size += rep[i] * xsize(rep[i + 1]);
              i++;
            }
          }
          const ret = new _Mem3vl(bits, size, -1);
          let w = 0;
          const decode = (x) => {
            if (x.length == bits) {
              fromBinInternal(x, w, bits, ret._avec, ret._bvec);
              w += ret._wpc;
            } else if (x.length == hexlen) {
              fromHexInternal(x, w, bits, ret._avec, ret._bvec);
              w += ret._wpc;
            } else {
              for (let i = 0; i < x.length / hexlen; i++) {
                fromHexInternal(x.slice(i * hexlen, (i + 1) * hexlen), w, bits, ret._avec, ret._bvec);
                w += ret._wpc;
              }
            }
          };
          for (let i = 0; i < rep.length; i++) {
            if (typeof rep[i] === "string")
              decode(rep[i]);
            else if (typeof rep[i] === "number") {
              for (const j of Array(rep[i]).keys())
                decode(rep[i + 1]);
              i++;
            }
          }
          return ret;
        }
        toArray() {
          return Array(this._size).fill(0).map((a, i) => this.get(i));
        }
        toHex() {
          return this.toArray().map((x) => x.toHex());
        }
        eq(m) {
          if (m._bits != this._bits || m._size != this._size)
            return false;
          for (let i = 0; i < this._size; i++)
            if (!m.get(i).eq(this.get(i)))
              return false;
          return true;
        }
      };
      exports.Mem3vl = Mem3vl;
      var Display3vlWithRegex = class {
        constructor(pattern) {
          _Display3vlWithRegex_regex.set(this, void 0);
          this.pattern = pattern;
          __classPrivateFieldSet(this, _Display3vlWithRegex_regex, RegExp("^(?:" + this.pattern + ")$"), "f");
        }
        validate(data, bits) {
          return __classPrivateFieldGet(this, _Display3vlWithRegex_regex, "f").test(data);
        }
      };
      exports.Display3vlWithRegex = Display3vlWithRegex;
      _Display3vlWithRegex_regex = /* @__PURE__ */ new WeakMap();
      var Display3vlHex = class extends Display3vlWithRegex {
        constructor() {
          super("[0-9a-fx]*");
          this.name = "hex";
          this.sort = 0;
        }
        can(kind, bits) {
          return true;
        }
        read(data, bits) {
          return Vector3vl.fromHex(data, bits);
        }
        show(data) {
          return data.toHex();
        }
        size(bits) {
          return Math.ceil(bits / 4);
        }
      };
      exports.Display3vlHex = Display3vlHex;
      var Display3vlBin = class extends Display3vlWithRegex {
        constructor() {
          super("[01x]*");
          this.name = "bin";
          this.sort = 0;
        }
        can(kind, bits) {
          return true;
        }
        read(data, bits) {
          return Vector3vl.fromBin(data, bits);
        }
        show(data) {
          return data.toBin();
        }
        size(bits) {
          return bits;
        }
      };
      exports.Display3vlBin = Display3vlBin;
      var Display3vlOct = class extends Display3vlWithRegex {
        constructor() {
          super("[0-7x]*");
          this.name = "oct";
          this.sort = 0;
        }
        can(kind, bits) {
          return true;
        }
        read(data, bits) {
          return Vector3vl.fromOct(data, bits);
        }
        show(data) {
          return data.toOct();
        }
        size(bits) {
          return Math.ceil(bits / 3);
        }
      };
      exports.Display3vlOct = Display3vlOct;
      var Display3vlDec = class extends Display3vlWithRegex {
        constructor() {
          super("[0-9]*|x");
        }
        get name() {
          return "dec";
        }
        get sort() {
          return 0;
        }
        can(kind, bits) {
          return true;
        }
        read(data, bits) {
          if (data == "x")
            return Vector3vl.xes(bits);
          return Vector3vl.fromNumber(BigInt(data), bits);
        }
        show(data) {
          if (!data.isFullyDefined)
            return "x";
          return data.toBigInt().toString();
        }
        size(bits) {
          return Math.max(1, Math.ceil(bits / Math.log2(10)));
        }
      };
      var Display3vlDec2c = class extends Display3vlWithRegex {
        constructor() {
          super("-?[0-9]*|x");
        }
        get name() {
          return "dec2c";
        }
        get sort() {
          return 0;
        }
        can(kind, bits) {
          return bits > 0;
        }
        read(data, bits) {
          if (data == "x")
            return Vector3vl.xes(bits);
          return Vector3vl.fromNumber(BigInt(data), bits);
        }
        show(data) {
          if (!data.isFullyDefined)
            return "x";
          return data.toBigIntSigned().toString();
        }
        size(bits) {
          return 1 + Math.ceil(bits / Math.log2(10));
        }
      };
      var Display3vl = class {
        constructor() {
          this.displays = {};
          this.addDisplay(new Display3vlHex());
          this.addDisplay(new Display3vlBin());
          this.addDisplay(new Display3vlOct());
          this.addDisplay(new Display3vlDec());
          this.addDisplay(new Display3vlDec2c());
        }
        addDisplay(display) {
          this.displays[display.name] = display;
        }
        usableDisplays(kind, bits) {
          const ret = [];
          for (let iface of Object.values(this.displays)) {
            if (iface.can(kind, bits))
              ret.push(iface);
          }
          return ret.sort((x, y) => x.sort - y.sort ? x.sort - y.sort : x.name.localeCompare(y.name)).map((x) => x.name);
        }
        show(name, data) {
          return this.displays[name].show(data);
        }
        read(name, data, bits) {
          return this.displays[name].read(data, bits);
        }
        pattern(name) {
          return this.displays[name].pattern;
        }
        validate(name, data, bits) {
          return this.displays[name].validate(data, bits);
        }
        size(name, bits) {
          return this.displays[name].size(bits);
        }
      };
      exports.Display3vl = Display3vl;
    }
  });

  // node_modules/topsort/lib/topsort.js
  var require_topsort = __commonJS({
    "node_modules/topsort/lib/topsort.js"(exports, module) {
      var EdgeNode = /* @__PURE__ */ (function() {
        function EdgeNode2(id) {
          this.id = id;
          this.afters = [];
        }
        return EdgeNode2;
      })();
      function sortDesc(a, b) {
        if (a < b)
          return 1;
        if (a > b)
          return -1;
        return 0;
      }
      function topsort(edges, options) {
        var nodes = {};
        options = options || { continueOnCircularDependency: false };
        var sorted = [];
        var visited = {};
        edges.forEach(function(edge) {
          var fromEdge = edge[0];
          var fromStr = fromEdge.toString();
          var fromNode;
          if (!(fromNode = nodes[fromStr])) {
            fromNode = nodes[fromStr] = new EdgeNode(fromEdge);
          }
          edge.forEach(function(toEdge) {
            if (toEdge == fromEdge) {
              return;
            }
            var toEdgeStr = toEdge.toString();
            if (!nodes[toEdgeStr]) {
              nodes[toEdgeStr] = new EdgeNode(toEdge);
            }
            fromNode.afters.push(toEdge);
          });
        });
        var keys = Object.keys(nodes);
        keys.sort(sortDesc);
        keys.forEach(function visit(idstr, ancestorsIn) {
          var node = nodes[idstr];
          var id = node.id;
          if (visited[idstr]) {
            return;
          }
          var ancestors = Array.isArray(ancestorsIn) ? ancestorsIn : [];
          ancestors.push(id);
          visited[idstr] = true;
          node.afters.sort(sortDesc);
          node.afters.forEach(function(afterID) {
            if (ancestors.indexOf(afterID) >= 0) {
              if (options.continueOnCircularDependency) {
                return;
              }
              throw new Error("Circular chain found: " + id + " must be before " + afterID + " due to a direct order specification, but " + afterID + " must be before " + id + " based on other specifications.");
            }
            visit(afterID.toString(), ancestors.map(function(v) {
              return v;
            }));
          });
          sorted.unshift(id);
        });
        return sorted;
      }
      module.exports = topsort;
    }
  });

  // node_modules/has-symbols/shams.js
  var require_shams = __commonJS({
    "node_modules/has-symbols/shams.js"(exports, module) {
      "use strict";
      module.exports = function hasSymbols() {
        if (typeof Symbol !== "function" || typeof Object.getOwnPropertySymbols !== "function") {
          return false;
        }
        if (typeof Symbol.iterator === "symbol") {
          return true;
        }
        var obj = {};
        var sym = /* @__PURE__ */ Symbol("test");
        var symObj = Object(sym);
        if (typeof sym === "string") {
          return false;
        }
        if (Object.prototype.toString.call(sym) !== "[object Symbol]") {
          return false;
        }
        if (Object.prototype.toString.call(symObj) !== "[object Symbol]") {
          return false;
        }
        var symVal = 42;
        obj[sym] = symVal;
        for (var _ in obj) {
          return false;
        }
        if (typeof Object.keys === "function" && Object.keys(obj).length !== 0) {
          return false;
        }
        if (typeof Object.getOwnPropertyNames === "function" && Object.getOwnPropertyNames(obj).length !== 0) {
          return false;
        }
        var syms = Object.getOwnPropertySymbols(obj);
        if (syms.length !== 1 || syms[0] !== sym) {
          return false;
        }
        if (!Object.prototype.propertyIsEnumerable.call(obj, sym)) {
          return false;
        }
        if (typeof Object.getOwnPropertyDescriptor === "function") {
          var descriptor = (
            /** @type {PropertyDescriptor} */
            Object.getOwnPropertyDescriptor(obj, sym)
          );
          if (descriptor.value !== symVal || descriptor.enumerable !== true) {
            return false;
          }
        }
        return true;
      };
    }
  });

  // node_modules/has-tostringtag/shams.js
  var require_shams2 = __commonJS({
    "node_modules/has-tostringtag/shams.js"(exports, module) {
      "use strict";
      var hasSymbols = require_shams();
      module.exports = function hasToStringTagShams() {
        return hasSymbols() && !!Symbol.toStringTag;
      };
    }
  });

  // node_modules/es-object-atoms/index.js
  var require_es_object_atoms = __commonJS({
    "node_modules/es-object-atoms/index.js"(exports, module) {
      "use strict";
      module.exports = Object;
    }
  });

  // node_modules/es-errors/index.js
  var require_es_errors = __commonJS({
    "node_modules/es-errors/index.js"(exports, module) {
      "use strict";
      module.exports = Error;
    }
  });

  // node_modules/es-errors/eval.js
  var require_eval = __commonJS({
    "node_modules/es-errors/eval.js"(exports, module) {
      "use strict";
      module.exports = EvalError;
    }
  });

  // node_modules/es-errors/range.js
  var require_range = __commonJS({
    "node_modules/es-errors/range.js"(exports, module) {
      "use strict";
      module.exports = RangeError;
    }
  });

  // node_modules/es-errors/ref.js
  var require_ref = __commonJS({
    "node_modules/es-errors/ref.js"(exports, module) {
      "use strict";
      module.exports = ReferenceError;
    }
  });

  // node_modules/es-errors/syntax.js
  var require_syntax = __commonJS({
    "node_modules/es-errors/syntax.js"(exports, module) {
      "use strict";
      module.exports = SyntaxError;
    }
  });

  // node_modules/es-errors/type.js
  var require_type = __commonJS({
    "node_modules/es-errors/type.js"(exports, module) {
      "use strict";
      module.exports = TypeError;
    }
  });

  // node_modules/es-errors/uri.js
  var require_uri = __commonJS({
    "node_modules/es-errors/uri.js"(exports, module) {
      "use strict";
      module.exports = URIError;
    }
  });

  // node_modules/math-intrinsics/abs.js
  var require_abs = __commonJS({
    "node_modules/math-intrinsics/abs.js"(exports, module) {
      "use strict";
      module.exports = Math.abs;
    }
  });

  // node_modules/math-intrinsics/floor.js
  var require_floor = __commonJS({
    "node_modules/math-intrinsics/floor.js"(exports, module) {
      "use strict";
      module.exports = Math.floor;
    }
  });

  // node_modules/math-intrinsics/max.js
  var require_max = __commonJS({
    "node_modules/math-intrinsics/max.js"(exports, module) {
      "use strict";
      module.exports = Math.max;
    }
  });

  // node_modules/math-intrinsics/min.js
  var require_min = __commonJS({
    "node_modules/math-intrinsics/min.js"(exports, module) {
      "use strict";
      module.exports = Math.min;
    }
  });

  // node_modules/math-intrinsics/pow.js
  var require_pow = __commonJS({
    "node_modules/math-intrinsics/pow.js"(exports, module) {
      "use strict";
      module.exports = Math.pow;
    }
  });

  // node_modules/math-intrinsics/round.js
  var require_round = __commonJS({
    "node_modules/math-intrinsics/round.js"(exports, module) {
      "use strict";
      module.exports = Math.round;
    }
  });

  // node_modules/math-intrinsics/isNaN.js
  var require_isNaN = __commonJS({
    "node_modules/math-intrinsics/isNaN.js"(exports, module) {
      "use strict";
      module.exports = Number.isNaN || function isNaN2(a) {
        return a !== a;
      };
    }
  });

  // node_modules/math-intrinsics/sign.js
  var require_sign = __commonJS({
    "node_modules/math-intrinsics/sign.js"(exports, module) {
      "use strict";
      var $isNaN = require_isNaN();
      module.exports = function sign(number) {
        if ($isNaN(number) || number === 0) {
          return number;
        }
        return number < 0 ? -1 : 1;
      };
    }
  });

  // node_modules/gopd/gOPD.js
  var require_gOPD = __commonJS({
    "node_modules/gopd/gOPD.js"(exports, module) {
      "use strict";
      module.exports = Object.getOwnPropertyDescriptor;
    }
  });

  // node_modules/gopd/index.js
  var require_gopd = __commonJS({
    "node_modules/gopd/index.js"(exports, module) {
      "use strict";
      var $gOPD = require_gOPD();
      if ($gOPD) {
        try {
          $gOPD([], "length");
        } catch (e) {
          $gOPD = null;
        }
      }
      module.exports = $gOPD;
    }
  });

  // node_modules/es-define-property/index.js
  var require_es_define_property = __commonJS({
    "node_modules/es-define-property/index.js"(exports, module) {
      "use strict";
      var $defineProperty = Object.defineProperty || false;
      if ($defineProperty) {
        try {
          $defineProperty({}, "a", { value: 1 });
        } catch (e) {
          $defineProperty = false;
        }
      }
      module.exports = $defineProperty;
    }
  });

  // node_modules/has-symbols/index.js
  var require_has_symbols = __commonJS({
    "node_modules/has-symbols/index.js"(exports, module) {
      "use strict";
      var origSymbol = typeof Symbol !== "undefined" && Symbol;
      var hasSymbolSham = require_shams();
      module.exports = function hasNativeSymbols() {
        if (typeof origSymbol !== "function") {
          return false;
        }
        if (typeof Symbol !== "function") {
          return false;
        }
        if (typeof origSymbol("foo") !== "symbol") {
          return false;
        }
        if (typeof /* @__PURE__ */ Symbol("bar") !== "symbol") {
          return false;
        }
        return hasSymbolSham();
      };
    }
  });

  // node_modules/get-proto/Reflect.getPrototypeOf.js
  var require_Reflect_getPrototypeOf = __commonJS({
    "node_modules/get-proto/Reflect.getPrototypeOf.js"(exports, module) {
      "use strict";
      module.exports = typeof Reflect !== "undefined" && Reflect.getPrototypeOf || null;
    }
  });

  // node_modules/get-proto/Object.getPrototypeOf.js
  var require_Object_getPrototypeOf = __commonJS({
    "node_modules/get-proto/Object.getPrototypeOf.js"(exports, module) {
      "use strict";
      var $Object = require_es_object_atoms();
      module.exports = $Object.getPrototypeOf || null;
    }
  });

  // node_modules/function-bind/implementation.js
  var require_implementation = __commonJS({
    "node_modules/function-bind/implementation.js"(exports, module) {
      "use strict";
      var ERROR_MESSAGE = "Function.prototype.bind called on incompatible ";
      var toStr = Object.prototype.toString;
      var max = Math.max;
      var funcType = "[object Function]";
      var concatty = function concatty2(a, b) {
        var arr = [];
        for (var i = 0; i < a.length; i += 1) {
          arr[i] = a[i];
        }
        for (var j = 0; j < b.length; j += 1) {
          arr[j + a.length] = b[j];
        }
        return arr;
      };
      var slicy = function slicy2(arrLike, offset) {
        var arr = [];
        for (var i = offset || 0, j = 0; i < arrLike.length; i += 1, j += 1) {
          arr[j] = arrLike[i];
        }
        return arr;
      };
      var joiny = function(arr, joiner) {
        var str = "";
        for (var i = 0; i < arr.length; i += 1) {
          str += arr[i];
          if (i + 1 < arr.length) {
            str += joiner;
          }
        }
        return str;
      };
      module.exports = function bind(that) {
        var target = this;
        if (typeof target !== "function" || toStr.apply(target) !== funcType) {
          throw new TypeError(ERROR_MESSAGE + target);
        }
        var args = slicy(arguments, 1);
        var bound;
        var binder = function() {
          if (this instanceof bound) {
            var result = target.apply(
              this,
              concatty(args, arguments)
            );
            if (Object(result) === result) {
              return result;
            }
            return this;
          }
          return target.apply(
            that,
            concatty(args, arguments)
          );
        };
        var boundLength = max(0, target.length - args.length);
        var boundArgs = [];
        for (var i = 0; i < boundLength; i++) {
          boundArgs[i] = "$" + i;
        }
        bound = Function("binder", "return function (" + joiny(boundArgs, ",") + "){ return binder.apply(this,arguments); }")(binder);
        if (target.prototype) {
          var Empty = function Empty2() {
          };
          Empty.prototype = target.prototype;
          bound.prototype = new Empty();
          Empty.prototype = null;
        }
        return bound;
      };
    }
  });

  // node_modules/function-bind/index.js
  var require_function_bind = __commonJS({
    "node_modules/function-bind/index.js"(exports, module) {
      "use strict";
      var implementation = require_implementation();
      module.exports = Function.prototype.bind || implementation;
    }
  });

  // node_modules/call-bind-apply-helpers/functionCall.js
  var require_functionCall = __commonJS({
    "node_modules/call-bind-apply-helpers/functionCall.js"(exports, module) {
      "use strict";
      module.exports = Function.prototype.call;
    }
  });

  // node_modules/call-bind-apply-helpers/functionApply.js
  var require_functionApply = __commonJS({
    "node_modules/call-bind-apply-helpers/functionApply.js"(exports, module) {
      "use strict";
      module.exports = Function.prototype.apply;
    }
  });

  // node_modules/call-bind-apply-helpers/reflectApply.js
  var require_reflectApply = __commonJS({
    "node_modules/call-bind-apply-helpers/reflectApply.js"(exports, module) {
      "use strict";
      module.exports = typeof Reflect !== "undefined" && Reflect && Reflect.apply;
    }
  });

  // node_modules/call-bind-apply-helpers/actualApply.js
  var require_actualApply = __commonJS({
    "node_modules/call-bind-apply-helpers/actualApply.js"(exports, module) {
      "use strict";
      var bind = require_function_bind();
      var $apply = require_functionApply();
      var $call = require_functionCall();
      var $reflectApply = require_reflectApply();
      module.exports = $reflectApply || bind.call($call, $apply);
    }
  });

  // node_modules/call-bind-apply-helpers/index.js
  var require_call_bind_apply_helpers = __commonJS({
    "node_modules/call-bind-apply-helpers/index.js"(exports, module) {
      "use strict";
      var bind = require_function_bind();
      var $TypeError = require_type();
      var $call = require_functionCall();
      var $actualApply = require_actualApply();
      module.exports = function callBindBasic(args) {
        if (args.length < 1 || typeof args[0] !== "function") {
          throw new $TypeError("a function is required");
        }
        return $actualApply(bind, $call, args);
      };
    }
  });

  // node_modules/dunder-proto/get.js
  var require_get = __commonJS({
    "node_modules/dunder-proto/get.js"(exports, module) {
      "use strict";
      var callBind = require_call_bind_apply_helpers();
      var gOPD = require_gopd();
      var hasProtoAccessor;
      try {
        hasProtoAccessor = /** @type {{ __proto__?: typeof Array.prototype }} */
        [].__proto__ === Array.prototype;
      } catch (e) {
        if (!e || typeof e !== "object" || !("code" in e) || e.code !== "ERR_PROTO_ACCESS") {
          throw e;
        }
      }
      var desc = !!hasProtoAccessor && gOPD && gOPD(
        Object.prototype,
        /** @type {keyof typeof Object.prototype} */
        "__proto__"
      );
      var $Object = Object;
      var $getPrototypeOf = $Object.getPrototypeOf;
      module.exports = desc && typeof desc.get === "function" ? callBind([desc.get]) : typeof $getPrototypeOf === "function" ? (
        /** @type {import('./get')} */
        function getDunder(value) {
          return $getPrototypeOf(value == null ? value : $Object(value));
        }
      ) : false;
    }
  });

  // node_modules/get-proto/index.js
  var require_get_proto = __commonJS({
    "node_modules/get-proto/index.js"(exports, module) {
      "use strict";
      var reflectGetProto = require_Reflect_getPrototypeOf();
      var originalGetProto = require_Object_getPrototypeOf();
      var getDunderProto = require_get();
      module.exports = reflectGetProto ? function getProto(O) {
        return reflectGetProto(O);
      } : originalGetProto ? function getProto(O) {
        if (!O || typeof O !== "object" && typeof O !== "function") {
          throw new TypeError("getProto: not an object");
        }
        return originalGetProto(O);
      } : getDunderProto ? function getProto(O) {
        return getDunderProto(O);
      } : null;
    }
  });

  // node_modules/hasown/index.js
  var require_hasown = __commonJS({
    "node_modules/hasown/index.js"(exports, module) {
      "use strict";
      var call = Function.prototype.call;
      var $hasOwn = Object.prototype.hasOwnProperty;
      var bind = require_function_bind();
      module.exports = bind.call(call, $hasOwn);
    }
  });

  // node_modules/get-intrinsic/index.js
  var require_get_intrinsic = __commonJS({
    "node_modules/get-intrinsic/index.js"(exports, module) {
      "use strict";
      var undefined2;
      var $Object = require_es_object_atoms();
      var $Error = require_es_errors();
      var $EvalError = require_eval();
      var $RangeError = require_range();
      var $ReferenceError = require_ref();
      var $SyntaxError = require_syntax();
      var $TypeError = require_type();
      var $URIError = require_uri();
      var abs = require_abs();
      var floor = require_floor();
      var max = require_max();
      var min = require_min();
      var pow = require_pow();
      var round = require_round();
      var sign = require_sign();
      var $Function = Function;
      var getEvalledConstructor = function(expressionSyntax) {
        try {
          return $Function('"use strict"; return (' + expressionSyntax + ").constructor;")();
        } catch (e) {
        }
      };
      var $gOPD = require_gopd();
      var $defineProperty = require_es_define_property();
      var throwTypeError = function() {
        throw new $TypeError();
      };
      var ThrowTypeError = $gOPD ? (function() {
        try {
          arguments.callee;
          return throwTypeError;
        } catch (calleeThrows) {
          try {
            return $gOPD(arguments, "callee").get;
          } catch (gOPDthrows) {
            return throwTypeError;
          }
        }
      })() : throwTypeError;
      var hasSymbols = require_has_symbols()();
      var getProto = require_get_proto();
      var $ObjectGPO = require_Object_getPrototypeOf();
      var $ReflectGPO = require_Reflect_getPrototypeOf();
      var $apply = require_functionApply();
      var $call = require_functionCall();
      var needsEval = {};
      var TypedArray = typeof Uint8Array === "undefined" || !getProto ? undefined2 : getProto(Uint8Array);
      var INTRINSICS = {
        __proto__: null,
        "%AggregateError%": typeof AggregateError === "undefined" ? undefined2 : AggregateError,
        "%Array%": Array,
        "%ArrayBuffer%": typeof ArrayBuffer === "undefined" ? undefined2 : ArrayBuffer,
        "%ArrayIteratorPrototype%": hasSymbols && getProto ? getProto([][Symbol.iterator]()) : undefined2,
        "%AsyncFromSyncIteratorPrototype%": undefined2,
        "%AsyncFunction%": needsEval,
        "%AsyncGenerator%": needsEval,
        "%AsyncGeneratorFunction%": needsEval,
        "%AsyncIteratorPrototype%": needsEval,
        "%Atomics%": typeof Atomics === "undefined" ? undefined2 : Atomics,
        "%BigInt%": typeof BigInt === "undefined" ? undefined2 : BigInt,
        "%BigInt64Array%": typeof BigInt64Array === "undefined" ? undefined2 : BigInt64Array,
        "%BigUint64Array%": typeof BigUint64Array === "undefined" ? undefined2 : BigUint64Array,
        "%Boolean%": Boolean,
        "%DataView%": typeof DataView === "undefined" ? undefined2 : DataView,
        "%Date%": Date,
        "%decodeURI%": decodeURI,
        "%decodeURIComponent%": decodeURIComponent,
        "%encodeURI%": encodeURI,
        "%encodeURIComponent%": encodeURIComponent,
        "%Error%": $Error,
        "%eval%": eval,
        // eslint-disable-line no-eval
        "%EvalError%": $EvalError,
        "%Float16Array%": typeof Float16Array === "undefined" ? undefined2 : Float16Array,
        "%Float32Array%": typeof Float32Array === "undefined" ? undefined2 : Float32Array,
        "%Float64Array%": typeof Float64Array === "undefined" ? undefined2 : Float64Array,
        "%FinalizationRegistry%": typeof FinalizationRegistry === "undefined" ? undefined2 : FinalizationRegistry,
        "%Function%": $Function,
        "%GeneratorFunction%": needsEval,
        "%Int8Array%": typeof Int8Array === "undefined" ? undefined2 : Int8Array,
        "%Int16Array%": typeof Int16Array === "undefined" ? undefined2 : Int16Array,
        "%Int32Array%": typeof Int32Array === "undefined" ? undefined2 : Int32Array,
        "%isFinite%": isFinite,
        "%isNaN%": isNaN,
        "%IteratorPrototype%": hasSymbols && getProto ? getProto(getProto([][Symbol.iterator]())) : undefined2,
        "%JSON%": typeof JSON === "object" ? JSON : undefined2,
        "%Map%": typeof Map === "undefined" ? undefined2 : Map,
        "%MapIteratorPrototype%": typeof Map === "undefined" || !hasSymbols || !getProto ? undefined2 : getProto((/* @__PURE__ */ new Map())[Symbol.iterator]()),
        "%Math%": Math,
        "%Number%": Number,
        "%Object%": $Object,
        "%Object.getOwnPropertyDescriptor%": $gOPD,
        "%parseFloat%": parseFloat,
        "%parseInt%": parseInt,
        "%Promise%": typeof Promise === "undefined" ? undefined2 : Promise,
        "%Proxy%": typeof Proxy === "undefined" ? undefined2 : Proxy,
        "%RangeError%": $RangeError,
        "%ReferenceError%": $ReferenceError,
        "%Reflect%": typeof Reflect === "undefined" ? undefined2 : Reflect,
        "%RegExp%": RegExp,
        "%Set%": typeof Set === "undefined" ? undefined2 : Set,
        "%SetIteratorPrototype%": typeof Set === "undefined" || !hasSymbols || !getProto ? undefined2 : getProto((/* @__PURE__ */ new Set())[Symbol.iterator]()),
        "%SharedArrayBuffer%": typeof SharedArrayBuffer === "undefined" ? undefined2 : SharedArrayBuffer,
        "%String%": String,
        "%StringIteratorPrototype%": hasSymbols && getProto ? getProto(""[Symbol.iterator]()) : undefined2,
        "%Symbol%": hasSymbols ? Symbol : undefined2,
        "%SyntaxError%": $SyntaxError,
        "%ThrowTypeError%": ThrowTypeError,
        "%TypedArray%": TypedArray,
        "%TypeError%": $TypeError,
        "%Uint8Array%": typeof Uint8Array === "undefined" ? undefined2 : Uint8Array,
        "%Uint8ClampedArray%": typeof Uint8ClampedArray === "undefined" ? undefined2 : Uint8ClampedArray,
        "%Uint16Array%": typeof Uint16Array === "undefined" ? undefined2 : Uint16Array,
        "%Uint32Array%": typeof Uint32Array === "undefined" ? undefined2 : Uint32Array,
        "%URIError%": $URIError,
        "%WeakMap%": typeof WeakMap === "undefined" ? undefined2 : WeakMap,
        "%WeakRef%": typeof WeakRef === "undefined" ? undefined2 : WeakRef,
        "%WeakSet%": typeof WeakSet === "undefined" ? undefined2 : WeakSet,
        "%Function.prototype.call%": $call,
        "%Function.prototype.apply%": $apply,
        "%Object.defineProperty%": $defineProperty,
        "%Object.getPrototypeOf%": $ObjectGPO,
        "%Math.abs%": abs,
        "%Math.floor%": floor,
        "%Math.max%": max,
        "%Math.min%": min,
        "%Math.pow%": pow,
        "%Math.round%": round,
        "%Math.sign%": sign,
        "%Reflect.getPrototypeOf%": $ReflectGPO
      };
      if (getProto) {
        try {
          null.error;
        } catch (e) {
          errorProto = getProto(getProto(e));
          INTRINSICS["%Error.prototype%"] = errorProto;
        }
      }
      var errorProto;
      var doEval = function doEval2(name) {
        var value;
        if (name === "%AsyncFunction%") {
          value = getEvalledConstructor("async function () {}");
        } else if (name === "%GeneratorFunction%") {
          value = getEvalledConstructor("function* () {}");
        } else if (name === "%AsyncGeneratorFunction%") {
          value = getEvalledConstructor("async function* () {}");
        } else if (name === "%AsyncGenerator%") {
          var fn = doEval2("%AsyncGeneratorFunction%");
          if (fn) {
            value = fn.prototype;
          }
        } else if (name === "%AsyncIteratorPrototype%") {
          var gen = doEval2("%AsyncGenerator%");
          if (gen && getProto) {
            value = getProto(gen.prototype);
          }
        }
        INTRINSICS[name] = value;
        return value;
      };
      var LEGACY_ALIASES = {
        __proto__: null,
        "%ArrayBufferPrototype%": ["ArrayBuffer", "prototype"],
        "%ArrayPrototype%": ["Array", "prototype"],
        "%ArrayProto_entries%": ["Array", "prototype", "entries"],
        "%ArrayProto_forEach%": ["Array", "prototype", "forEach"],
        "%ArrayProto_keys%": ["Array", "prototype", "keys"],
        "%ArrayProto_values%": ["Array", "prototype", "values"],
        "%AsyncFunctionPrototype%": ["AsyncFunction", "prototype"],
        "%AsyncGenerator%": ["AsyncGeneratorFunction", "prototype"],
        "%AsyncGeneratorPrototype%": ["AsyncGeneratorFunction", "prototype", "prototype"],
        "%BooleanPrototype%": ["Boolean", "prototype"],
        "%DataViewPrototype%": ["DataView", "prototype"],
        "%DatePrototype%": ["Date", "prototype"],
        "%ErrorPrototype%": ["Error", "prototype"],
        "%EvalErrorPrototype%": ["EvalError", "prototype"],
        "%Float32ArrayPrototype%": ["Float32Array", "prototype"],
        "%Float64ArrayPrototype%": ["Float64Array", "prototype"],
        "%FunctionPrototype%": ["Function", "prototype"],
        "%Generator%": ["GeneratorFunction", "prototype"],
        "%GeneratorPrototype%": ["GeneratorFunction", "prototype", "prototype"],
        "%Int8ArrayPrototype%": ["Int8Array", "prototype"],
        "%Int16ArrayPrototype%": ["Int16Array", "prototype"],
        "%Int32ArrayPrototype%": ["Int32Array", "prototype"],
        "%JSONParse%": ["JSON", "parse"],
        "%JSONStringify%": ["JSON", "stringify"],
        "%MapPrototype%": ["Map", "prototype"],
        "%NumberPrototype%": ["Number", "prototype"],
        "%ObjectPrototype%": ["Object", "prototype"],
        "%ObjProto_toString%": ["Object", "prototype", "toString"],
        "%ObjProto_valueOf%": ["Object", "prototype", "valueOf"],
        "%PromisePrototype%": ["Promise", "prototype"],
        "%PromiseProto_then%": ["Promise", "prototype", "then"],
        "%Promise_all%": ["Promise", "all"],
        "%Promise_reject%": ["Promise", "reject"],
        "%Promise_resolve%": ["Promise", "resolve"],
        "%RangeErrorPrototype%": ["RangeError", "prototype"],
        "%ReferenceErrorPrototype%": ["ReferenceError", "prototype"],
        "%RegExpPrototype%": ["RegExp", "prototype"],
        "%SetPrototype%": ["Set", "prototype"],
        "%SharedArrayBufferPrototype%": ["SharedArrayBuffer", "prototype"],
        "%StringPrototype%": ["String", "prototype"],
        "%SymbolPrototype%": ["Symbol", "prototype"],
        "%SyntaxErrorPrototype%": ["SyntaxError", "prototype"],
        "%TypedArrayPrototype%": ["TypedArray", "prototype"],
        "%TypeErrorPrototype%": ["TypeError", "prototype"],
        "%Uint8ArrayPrototype%": ["Uint8Array", "prototype"],
        "%Uint8ClampedArrayPrototype%": ["Uint8ClampedArray", "prototype"],
        "%Uint16ArrayPrototype%": ["Uint16Array", "prototype"],
        "%Uint32ArrayPrototype%": ["Uint32Array", "prototype"],
        "%URIErrorPrototype%": ["URIError", "prototype"],
        "%WeakMapPrototype%": ["WeakMap", "prototype"],
        "%WeakSetPrototype%": ["WeakSet", "prototype"]
      };
      var bind = require_function_bind();
      var hasOwn = require_hasown();
      var $concat = bind.call($call, Array.prototype.concat);
      var $spliceApply = bind.call($apply, Array.prototype.splice);
      var $replace = bind.call($call, String.prototype.replace);
      var $strSlice = bind.call($call, String.prototype.slice);
      var $exec = bind.call($call, RegExp.prototype.exec);
      var rePropName = /[^%.[\]]+|\[(?:(-?\d+(?:\.\d+)?)|(["'])((?:(?!\2)[^\\]|\\.)*?)\2)\]|(?=(?:\.|\[\])(?:\.|\[\]|%$))/g;
      var reEscapeChar = /\\(\\)?/g;
      var stringToPath = function stringToPath2(string) {
        var first = $strSlice(string, 0, 1);
        var last = $strSlice(string, -1);
        if (first === "%" && last !== "%") {
          throw new $SyntaxError("invalid intrinsic syntax, expected closing `%`");
        } else if (last === "%" && first !== "%") {
          throw new $SyntaxError("invalid intrinsic syntax, expected opening `%`");
        }
        var result = [];
        $replace(string, rePropName, function(match, number, quote, subString) {
          result[result.length] = quote ? $replace(subString, reEscapeChar, "$1") : number || match;
        });
        return result;
      };
      var getBaseIntrinsic = function getBaseIntrinsic2(name, allowMissing) {
        var intrinsicName = name;
        var alias;
        if (hasOwn(LEGACY_ALIASES, intrinsicName)) {
          alias = LEGACY_ALIASES[intrinsicName];
          intrinsicName = "%" + alias[0] + "%";
        }
        if (hasOwn(INTRINSICS, intrinsicName)) {
          var value = INTRINSICS[intrinsicName];
          if (value === needsEval) {
            value = doEval(intrinsicName);
          }
          if (typeof value === "undefined" && !allowMissing) {
            throw new $TypeError("intrinsic " + name + " exists, but is not available. Please file an issue!");
          }
          return {
            alias,
            name: intrinsicName,
            value
          };
        }
        throw new $SyntaxError("intrinsic " + name + " does not exist!");
      };
      module.exports = function GetIntrinsic(name, allowMissing) {
        if (typeof name !== "string" || name.length === 0) {
          throw new $TypeError("intrinsic name must be a non-empty string");
        }
        if (arguments.length > 1 && typeof allowMissing !== "boolean") {
          throw new $TypeError('"allowMissing" argument must be a boolean');
        }
        if ($exec(/^%?[^%]*%?$/, name) === null) {
          throw new $SyntaxError("`%` may not be present anywhere but at the beginning and end of the intrinsic name");
        }
        var parts = stringToPath(name);
        var intrinsicBaseName = parts.length > 0 ? parts[0] : "";
        var intrinsic = getBaseIntrinsic("%" + intrinsicBaseName + "%", allowMissing);
        var intrinsicRealName = intrinsic.name;
        var value = intrinsic.value;
        var skipFurtherCaching = false;
        var alias = intrinsic.alias;
        if (alias) {
          intrinsicBaseName = alias[0];
          $spliceApply(parts, $concat([0, 1], alias));
        }
        for (var i = 1, isOwn = true; i < parts.length; i += 1) {
          var part = parts[i];
          var first = $strSlice(part, 0, 1);
          var last = $strSlice(part, -1);
          if ((first === '"' || first === "'" || first === "`" || (last === '"' || last === "'" || last === "`")) && first !== last) {
            throw new $SyntaxError("property names with quotes must have matching quotes");
          }
          if (part === "constructor" || !isOwn) {
            skipFurtherCaching = true;
          }
          intrinsicBaseName += "." + part;
          intrinsicRealName = "%" + intrinsicBaseName + "%";
          if (hasOwn(INTRINSICS, intrinsicRealName)) {
            value = INTRINSICS[intrinsicRealName];
          } else if (value != null) {
            if (!(part in value)) {
              if (!allowMissing) {
                throw new $TypeError("base intrinsic for " + name + " exists, but the property is not available.");
              }
              return void undefined2;
            }
            if ($gOPD && i + 1 >= parts.length) {
              var desc = $gOPD(value, part);
              isOwn = !!desc;
              if (isOwn && "get" in desc && !("originalValue" in desc.get)) {
                value = desc.get;
              } else {
                value = value[part];
              }
            } else {
              isOwn = hasOwn(value, part);
              value = value[part];
            }
            if (isOwn && !skipFurtherCaching) {
              INTRINSICS[intrinsicRealName] = value;
            }
          }
        }
        return value;
      };
    }
  });

  // node_modules/call-bound/index.js
  var require_call_bound = __commonJS({
    "node_modules/call-bound/index.js"(exports, module) {
      "use strict";
      var GetIntrinsic = require_get_intrinsic();
      var callBindBasic = require_call_bind_apply_helpers();
      var $indexOf = callBindBasic([GetIntrinsic("%String.prototype.indexOf%")]);
      module.exports = function callBoundIntrinsic(name, allowMissing) {
        var intrinsic = (
          /** @type {(this: unknown, ...args: unknown[]) => unknown} */
          GetIntrinsic(name, !!allowMissing)
        );
        if (typeof intrinsic === "function" && $indexOf(name, ".prototype.") > -1) {
          return callBindBasic(
            /** @type {const} */
            [intrinsic]
          );
        }
        return intrinsic;
      };
    }
  });

  // node_modules/is-arguments/index.js
  var require_is_arguments = __commonJS({
    "node_modules/is-arguments/index.js"(exports, module) {
      "use strict";
      var hasToStringTag = require_shams2()();
      var callBound = require_call_bound();
      var $toString = callBound("Object.prototype.toString");
      var isStandardArguments = function isArguments(value) {
        if (hasToStringTag && value && typeof value === "object" && Symbol.toStringTag in value) {
          return false;
        }
        return $toString(value) === "[object Arguments]";
      };
      var isLegacyArguments = function isArguments(value) {
        if (isStandardArguments(value)) {
          return true;
        }
        return value !== null && typeof value === "object" && "length" in value && typeof value.length === "number" && value.length >= 0 && $toString(value) !== "[object Array]" && "callee" in value && $toString(value.callee) === "[object Function]";
      };
      var supportsStandardArguments = (function() {
        return isStandardArguments(arguments);
      })();
      isStandardArguments.isLegacyArguments = isLegacyArguments;
      module.exports = supportsStandardArguments ? isStandardArguments : isLegacyArguments;
    }
  });

  // node_modules/is-regex/index.js
  var require_is_regex = __commonJS({
    "node_modules/is-regex/index.js"(exports, module) {
      "use strict";
      var callBound = require_call_bound();
      var hasToStringTag = require_shams2()();
      var hasOwn = require_hasown();
      var gOPD = require_gopd();
      var fn;
      if (hasToStringTag) {
        $exec = callBound("RegExp.prototype.exec");
        isRegexMarker = {};
        throwRegexMarker = function() {
          throw isRegexMarker;
        };
        badStringifier = {
          toString: throwRegexMarker,
          valueOf: throwRegexMarker
        };
        if (typeof Symbol.toPrimitive === "symbol") {
          badStringifier[Symbol.toPrimitive] = throwRegexMarker;
        }
        fn = function isRegex(value) {
          if (!value || typeof value !== "object") {
            return false;
          }
          var descriptor = (
            /** @type {NonNullable<typeof gOPD>} */
            gOPD(
              /** @type {{ lastIndex?: unknown }} */
              value,
              "lastIndex"
            )
          );
          var hasLastIndexDataProperty = descriptor && hasOwn(descriptor, "value");
          if (!hasLastIndexDataProperty) {
            return false;
          }
          try {
            $exec(
              value,
              /** @type {string} */
              /** @type {unknown} */
              badStringifier
            );
          } catch (e) {
            return e === isRegexMarker;
          }
        };
      } else {
        $toString = callBound("Object.prototype.toString");
        regexClass = "[object RegExp]";
        fn = function isRegex(value) {
          if (!value || typeof value !== "object" && typeof value !== "function") {
            return false;
          }
          return $toString(value) === regexClass;
        };
      }
      var $exec;
      var isRegexMarker;
      var throwRegexMarker;
      var badStringifier;
      var $toString;
      var regexClass;
      module.exports = fn;
    }
  });

  // node_modules/safe-regex-test/index.js
  var require_safe_regex_test = __commonJS({
    "node_modules/safe-regex-test/index.js"(exports, module) {
      "use strict";
      var callBound = require_call_bound();
      var isRegex = require_is_regex();
      var $exec = callBound("RegExp.prototype.exec");
      var $TypeError = require_type();
      module.exports = function regexTester(regex) {
        if (!isRegex(regex)) {
          throw new $TypeError("`regex` must be a RegExp");
        }
        return function test(s) {
          return $exec(regex, s) !== null;
        };
      };
    }
  });

  // node_modules/generator-function/index.js
  var require_generator_function = __commonJS({
    "node_modules/generator-function/index.js"(exports, module) {
      "use strict";
      var cached = (
        /** @type {GeneratorFunctionConstructor} */
        function* () {
        }.constructor
      );
      module.exports = () => cached;
    }
  });

  // node_modules/is-generator-function/index.js
  var require_is_generator_function = __commonJS({
    "node_modules/is-generator-function/index.js"(exports, module) {
      "use strict";
      var callBound = require_call_bound();
      var safeRegexTest = require_safe_regex_test();
      var isFnRegex = safeRegexTest(/^\s*(?:function)?\*/);
      var hasToStringTag = require_shams2()();
      var getProto = require_get_proto();
      var toStr = callBound("Object.prototype.toString");
      var fnToStr = callBound("Function.prototype.toString");
      var getGeneratorFunction = require_generator_function();
      module.exports = function isGeneratorFunction(fn) {
        if (typeof fn !== "function") {
          return false;
        }
        if (isFnRegex(fnToStr(fn))) {
          return true;
        }
        if (!hasToStringTag) {
          var str = toStr(fn);
          return str === "[object GeneratorFunction]";
        }
        if (!getProto) {
          return false;
        }
        var GeneratorFunction = getGeneratorFunction();
        return GeneratorFunction && getProto(fn) === GeneratorFunction.prototype;
      };
    }
  });

  // node_modules/is-callable/index.js
  var require_is_callable = __commonJS({
    "node_modules/is-callable/index.js"(exports, module) {
      "use strict";
      var fnToStr = Function.prototype.toString;
      var reflectApply = typeof Reflect === "object" && Reflect !== null && Reflect.apply;
      var badArrayLike;
      var isCallableMarker;
      if (typeof reflectApply === "function" && typeof Object.defineProperty === "function") {
        try {
          badArrayLike = Object.defineProperty({}, "length", {
            get: function() {
              throw isCallableMarker;
            }
          });
          isCallableMarker = {};
          reflectApply(function() {
            throw 42;
          }, null, badArrayLike);
        } catch (_) {
          if (_ !== isCallableMarker) {
            reflectApply = null;
          }
        }
      } else {
        reflectApply = null;
      }
      var constructorRegex = /^\s*class\b/;
      var isES6ClassFn = function isES6ClassFunction(value) {
        try {
          var fnStr = fnToStr.call(value);
          return constructorRegex.test(fnStr);
        } catch (e) {
          return false;
        }
      };
      var tryFunctionObject = function tryFunctionToStr(value) {
        try {
          if (isES6ClassFn(value)) {
            return false;
          }
          fnToStr.call(value);
          return true;
        } catch (e) {
          return false;
        }
      };
      var toStr = Object.prototype.toString;
      var objectClass = "[object Object]";
      var fnClass = "[object Function]";
      var genClass = "[object GeneratorFunction]";
      var ddaClass = "[object HTMLAllCollection]";
      var ddaClass2 = "[object HTML document.all class]";
      var ddaClass3 = "[object HTMLCollection]";
      var hasToStringTag = typeof Symbol === "function" && !!Symbol.toStringTag;
      var isIE68 = !(0 in [,]);
      var isDDA = function isDocumentDotAll() {
        return false;
      };
      if (typeof document === "object") {
        all = document.all;
        if (toStr.call(all) === toStr.call(document.all)) {
          isDDA = function isDocumentDotAll(value) {
            if ((isIE68 || !value) && (typeof value === "undefined" || typeof value === "object")) {
              try {
                var str = toStr.call(value);
                return (str === ddaClass || str === ddaClass2 || str === ddaClass3 || str === objectClass) && value("") == null;
              } catch (e) {
              }
            }
            return false;
          };
        }
      }
      var all;
      module.exports = reflectApply ? function isCallable(value) {
        if (isDDA(value)) {
          return true;
        }
        if (!value) {
          return false;
        }
        if (typeof value !== "function" && typeof value !== "object") {
          return false;
        }
        try {
          reflectApply(value, null, badArrayLike);
        } catch (e) {
          if (e !== isCallableMarker) {
            return false;
          }
        }
        return !isES6ClassFn(value) && tryFunctionObject(value);
      } : function isCallable(value) {
        if (isDDA(value)) {
          return true;
        }
        if (!value) {
          return false;
        }
        if (typeof value !== "function" && typeof value !== "object") {
          return false;
        }
        if (hasToStringTag) {
          return tryFunctionObject(value);
        }
        if (isES6ClassFn(value)) {
          return false;
        }
        var strClass = toStr.call(value);
        if (strClass !== fnClass && strClass !== genClass && !/^\[object HTML/.test(strClass)) {
          return false;
        }
        return tryFunctionObject(value);
      };
    }
  });

  // node_modules/for-each/index.js
  var require_for_each = __commonJS({
    "node_modules/for-each/index.js"(exports, module) {
      "use strict";
      var isCallable = require_is_callable();
      var toStr = Object.prototype.toString;
      var hasOwnProperty = Object.prototype.hasOwnProperty;
      var forEachArray = function forEachArray2(array, iterator, receiver) {
        for (var i = 0, len = array.length; i < len; i++) {
          if (hasOwnProperty.call(array, i)) {
            if (receiver == null) {
              iterator(array[i], i, array);
            } else {
              iterator.call(receiver, array[i], i, array);
            }
          }
        }
      };
      var forEachString = function forEachString2(string, iterator, receiver) {
        for (var i = 0, len = string.length; i < len; i++) {
          if (receiver == null) {
            iterator(string.charAt(i), i, string);
          } else {
            iterator.call(receiver, string.charAt(i), i, string);
          }
        }
      };
      var forEachObject = function forEachObject2(object, iterator, receiver) {
        for (var k in object) {
          if (hasOwnProperty.call(object, k)) {
            if (receiver == null) {
              iterator(object[k], k, object);
            } else {
              iterator.call(receiver, object[k], k, object);
            }
          }
        }
      };
      function isArray(x) {
        return toStr.call(x) === "[object Array]";
      }
      module.exports = function forEach(list, iterator, thisArg) {
        if (!isCallable(iterator)) {
          throw new TypeError("iterator must be a function");
        }
        var receiver;
        if (arguments.length >= 3) {
          receiver = thisArg;
        }
        if (isArray(list)) {
          forEachArray(list, iterator, receiver);
        } else if (typeof list === "string") {
          forEachString(list, iterator, receiver);
        } else {
          forEachObject(list, iterator, receiver);
        }
      };
    }
  });

  // node_modules/possible-typed-array-names/index.js
  var require_possible_typed_array_names = __commonJS({
    "node_modules/possible-typed-array-names/index.js"(exports, module) {
      "use strict";
      module.exports = [
        "Float16Array",
        "Float32Array",
        "Float64Array",
        "Int8Array",
        "Int16Array",
        "Int32Array",
        "Uint8Array",
        "Uint8ClampedArray",
        "Uint16Array",
        "Uint32Array",
        "BigInt64Array",
        "BigUint64Array"
      ];
    }
  });

  // node_modules/available-typed-arrays/index.js
  var require_available_typed_arrays = __commonJS({
    "node_modules/available-typed-arrays/index.js"(exports, module) {
      "use strict";
      var possibleNames = require_possible_typed_array_names();
      var g = typeof globalThis === "undefined" ? global : globalThis;
      module.exports = function availableTypedArrays() {
        var out = [];
        for (var i = 0; i < possibleNames.length; i++) {
          if (typeof g[possibleNames[i]] === "function") {
            out[out.length] = possibleNames[i];
          }
        }
        return out;
      };
    }
  });

  // node_modules/define-data-property/index.js
  var require_define_data_property = __commonJS({
    "node_modules/define-data-property/index.js"(exports, module) {
      "use strict";
      var $defineProperty = require_es_define_property();
      var $SyntaxError = require_syntax();
      var $TypeError = require_type();
      var gopd = require_gopd();
      module.exports = function defineDataProperty(obj, property, value) {
        if (!obj || typeof obj !== "object" && typeof obj !== "function") {
          throw new $TypeError("`obj` must be an object or a function`");
        }
        if (typeof property !== "string" && typeof property !== "symbol") {
          throw new $TypeError("`property` must be a string or a symbol`");
        }
        if (arguments.length > 3 && typeof arguments[3] !== "boolean" && arguments[3] !== null) {
          throw new $TypeError("`nonEnumerable`, if provided, must be a boolean or null");
        }
        if (arguments.length > 4 && typeof arguments[4] !== "boolean" && arguments[4] !== null) {
          throw new $TypeError("`nonWritable`, if provided, must be a boolean or null");
        }
        if (arguments.length > 5 && typeof arguments[5] !== "boolean" && arguments[5] !== null) {
          throw new $TypeError("`nonConfigurable`, if provided, must be a boolean or null");
        }
        if (arguments.length > 6 && typeof arguments[6] !== "boolean") {
          throw new $TypeError("`loose`, if provided, must be a boolean");
        }
        var nonEnumerable = arguments.length > 3 ? arguments[3] : null;
        var nonWritable = arguments.length > 4 ? arguments[4] : null;
        var nonConfigurable = arguments.length > 5 ? arguments[5] : null;
        var loose = arguments.length > 6 ? arguments[6] : false;
        var desc = !!gopd && gopd(obj, property);
        if ($defineProperty) {
          $defineProperty(obj, property, {
            configurable: nonConfigurable === null && desc ? desc.configurable : !nonConfigurable,
            enumerable: nonEnumerable === null && desc ? desc.enumerable : !nonEnumerable,
            value,
            writable: nonWritable === null && desc ? desc.writable : !nonWritable
          });
        } else if (loose || !nonEnumerable && !nonWritable && !nonConfigurable) {
          obj[property] = value;
        } else {
          throw new $SyntaxError("This environment does not support defining a property as non-configurable, non-writable, or non-enumerable.");
        }
      };
    }
  });

  // node_modules/has-property-descriptors/index.js
  var require_has_property_descriptors = __commonJS({
    "node_modules/has-property-descriptors/index.js"(exports, module) {
      "use strict";
      var $defineProperty = require_es_define_property();
      var hasPropertyDescriptors = function hasPropertyDescriptors2() {
        return !!$defineProperty;
      };
      hasPropertyDescriptors.hasArrayLengthDefineBug = function hasArrayLengthDefineBug() {
        if (!$defineProperty) {
          return null;
        }
        try {
          return $defineProperty([], "length", { value: 1 }).length !== 1;
        } catch (e) {
          return true;
        }
      };
      module.exports = hasPropertyDescriptors;
    }
  });

  // node_modules/set-function-length/index.js
  var require_set_function_length = __commonJS({
    "node_modules/set-function-length/index.js"(exports, module) {
      "use strict";
      var GetIntrinsic = require_get_intrinsic();
      var define2 = require_define_data_property();
      var hasDescriptors = require_has_property_descriptors()();
      var gOPD = require_gopd();
      var $TypeError = require_type();
      var $floor = GetIntrinsic("%Math.floor%");
      module.exports = function setFunctionLength(fn, length) {
        if (typeof fn !== "function") {
          throw new $TypeError("`fn` is not a function");
        }
        if (typeof length !== "number" || length < 0 || length > 4294967295 || $floor(length) !== length) {
          throw new $TypeError("`length` must be a positive 32-bit integer");
        }
        var loose = arguments.length > 2 && !!arguments[2];
        var functionLengthIsConfigurable = true;
        var functionLengthIsWritable = true;
        if ("length" in fn && gOPD) {
          var desc = gOPD(fn, "length");
          if (desc && !desc.configurable) {
            functionLengthIsConfigurable = false;
          }
          if (desc && !desc.writable) {
            functionLengthIsWritable = false;
          }
        }
        if (functionLengthIsConfigurable || functionLengthIsWritable || !loose) {
          if (hasDescriptors) {
            define2(
              /** @type {Parameters<define>[0]} */
              fn,
              "length",
              length,
              true,
              true
            );
          } else {
            define2(
              /** @type {Parameters<define>[0]} */
              fn,
              "length",
              length
            );
          }
        }
        return fn;
      };
    }
  });

  // node_modules/call-bind-apply-helpers/applyBind.js
  var require_applyBind = __commonJS({
    "node_modules/call-bind-apply-helpers/applyBind.js"(exports, module) {
      "use strict";
      var bind = require_function_bind();
      var $apply = require_functionApply();
      var actualApply = require_actualApply();
      module.exports = function applyBind() {
        return actualApply(bind, $apply, arguments);
      };
    }
  });

  // node_modules/call-bind/index.js
  var require_call_bind = __commonJS({
    "node_modules/call-bind/index.js"(exports, module) {
      "use strict";
      var setFunctionLength = require_set_function_length();
      var $defineProperty = require_es_define_property();
      var callBindBasic = require_call_bind_apply_helpers();
      var applyBind = require_applyBind();
      module.exports = function callBind(originalFunction) {
        var func = callBindBasic(arguments);
        var adjustedLength = 1 + originalFunction.length - (arguments.length - 1);
        return setFunctionLength(
          func,
          adjustedLength > 0 ? adjustedLength : 0,
          true
        );
      };
      if ($defineProperty) {
        $defineProperty(module.exports, "apply", { value: applyBind });
      } else {
        module.exports.apply = applyBind;
      }
    }
  });

  // node_modules/which-typed-array/index.js
  var require_which_typed_array = __commonJS({
    "node_modules/which-typed-array/index.js"(exports, module) {
      "use strict";
      var forEach = require_for_each();
      var availableTypedArrays = require_available_typed_arrays();
      var callBind = require_call_bind();
      var callBound = require_call_bound();
      var gOPD = require_gopd();
      var getProto = require_get_proto();
      var $toString = callBound("Object.prototype.toString");
      var hasToStringTag = require_shams2()();
      var g = typeof globalThis === "undefined" ? global : globalThis;
      var typedArrays = availableTypedArrays();
      var $slice = callBound("String.prototype.slice");
      var $indexOf = callBound("Array.prototype.indexOf", true) || function indexOf(array, value) {
        for (var i = 0; i < array.length; i += 1) {
          if (array[i] === value) {
            return i;
          }
        }
        return -1;
      };
      var cache = { __proto__: null };
      if (hasToStringTag && gOPD && getProto) {
        forEach(typedArrays, function(typedArray) {
          var arr = new g[typedArray]();
          if (Symbol.toStringTag in arr && getProto) {
            var proto = getProto(arr);
            var descriptor = gOPD(proto, Symbol.toStringTag);
            if (!descriptor && proto) {
              var superProto = getProto(proto);
              descriptor = gOPD(superProto, Symbol.toStringTag);
            }
            if (descriptor && descriptor.get) {
              var bound = callBind(descriptor.get);
              cache[
                /** @type {`$${TypedArrayName}`} */
                "$" + typedArray
              ] = bound;
            }
          }
        });
      } else {
        forEach(typedArrays, function(typedArray) {
          var arr = new g[typedArray]();
          var fn = arr.slice || arr.set;
          if (fn) {
            var bound = (
              /** @type {BoundSlice | BoundSet} */
              // @ts-expect-error TODO FIXME
              callBind(fn)
            );
            cache[
              /** @type {`$${TypedArrayName}`} */
              "$" + typedArray
            ] = bound;
          }
        });
      }
      function tryTypedArrays(value) {
        var found = false;
        forEach(
          /** @type {Record<`$${TypedArrayName}`, Getter>} */
          cache,
          /** @param {Getter} getter @param {`$${TypedArrayName}`} typedArray */
          function(getter, typedArray) {
            if (!found) {
              try {
                if ("$" + getter(value) === typedArray) {
                  found = /** @type {TypedArrayName} */
                  $slice(typedArray, 1);
                }
              } catch (e) {
              }
            }
          }
        );
        return found;
      }
      function trySlices(value) {
        var found = false;
        forEach(
          /** @type {Record<`$${TypedArrayName}`, Getter>} */
          cache,
          /** @param {Getter} getter @param {`$${TypedArrayName}`} name */
          function(getter, name) {
            if (!found) {
              try {
                getter(value);
                found = /** @type {TypedArrayName} */
                $slice(name, 1);
              } catch (e) {
              }
            }
          }
        );
        return found;
      }
      function isTATag(tag) {
        return $indexOf(typedArrays, tag) > -1;
      }
      module.exports = function whichTypedArray(value) {
        if (!value || typeof value !== "object") {
          return false;
        }
        if (!hasToStringTag) {
          var tag = $slice($toString(value), 8, -1);
          if (isTATag(tag)) {
            return tag;
          }
          if (tag !== "Object") {
            return false;
          }
          return trySlices(value);
        }
        if (!gOPD) {
          return null;
        }
        return tryTypedArrays(value);
      };
    }
  });

  // node_modules/is-typed-array/index.js
  var require_is_typed_array = __commonJS({
    "node_modules/is-typed-array/index.js"(exports, module) {
      "use strict";
      var whichTypedArray = require_which_typed_array();
      module.exports = function isTypedArray(value) {
        return !!whichTypedArray(value);
      };
    }
  });

  // node_modules/util/support/types.js
  var require_types = __commonJS({
    "node_modules/util/support/types.js"(exports) {
      "use strict";
      var isArgumentsObject = require_is_arguments();
      var isGeneratorFunction = require_is_generator_function();
      var whichTypedArray = require_which_typed_array();
      var isTypedArray = require_is_typed_array();
      function uncurryThis(f) {
        return f.call.bind(f);
      }
      var BigIntSupported = typeof BigInt !== "undefined";
      var SymbolSupported = typeof Symbol !== "undefined";
      var ObjectToString = uncurryThis(Object.prototype.toString);
      var numberValue = uncurryThis(Number.prototype.valueOf);
      var stringValue = uncurryThis(String.prototype.valueOf);
      var booleanValue = uncurryThis(Boolean.prototype.valueOf);
      if (BigIntSupported) {
        bigIntValue = uncurryThis(BigInt.prototype.valueOf);
      }
      var bigIntValue;
      if (SymbolSupported) {
        symbolValue = uncurryThis(Symbol.prototype.valueOf);
      }
      var symbolValue;
      function checkBoxedPrimitive(value, prototypeValueOf) {
        if (typeof value !== "object") {
          return false;
        }
        try {
          prototypeValueOf(value);
          return true;
        } catch (e) {
          return false;
        }
      }
      exports.isArgumentsObject = isArgumentsObject;
      exports.isGeneratorFunction = isGeneratorFunction;
      exports.isTypedArray = isTypedArray;
      function isPromise(input) {
        return typeof Promise !== "undefined" && input instanceof Promise || input !== null && typeof input === "object" && typeof input.then === "function" && typeof input.catch === "function";
      }
      exports.isPromise = isPromise;
      function isArrayBufferView(value) {
        if (typeof ArrayBuffer !== "undefined" && ArrayBuffer.isView) {
          return ArrayBuffer.isView(value);
        }
        return isTypedArray(value) || isDataView(value);
      }
      exports.isArrayBufferView = isArrayBufferView;
      function isUint8Array(value) {
        return whichTypedArray(value) === "Uint8Array";
      }
      exports.isUint8Array = isUint8Array;
      function isUint8ClampedArray(value) {
        return whichTypedArray(value) === "Uint8ClampedArray";
      }
      exports.isUint8ClampedArray = isUint8ClampedArray;
      function isUint16Array(value) {
        return whichTypedArray(value) === "Uint16Array";
      }
      exports.isUint16Array = isUint16Array;
      function isUint32Array(value) {
        return whichTypedArray(value) === "Uint32Array";
      }
      exports.isUint32Array = isUint32Array;
      function isInt8Array(value) {
        return whichTypedArray(value) === "Int8Array";
      }
      exports.isInt8Array = isInt8Array;
      function isInt16Array(value) {
        return whichTypedArray(value) === "Int16Array";
      }
      exports.isInt16Array = isInt16Array;
      function isInt32Array(value) {
        return whichTypedArray(value) === "Int32Array";
      }
      exports.isInt32Array = isInt32Array;
      function isFloat32Array(value) {
        return whichTypedArray(value) === "Float32Array";
      }
      exports.isFloat32Array = isFloat32Array;
      function isFloat64Array(value) {
        return whichTypedArray(value) === "Float64Array";
      }
      exports.isFloat64Array = isFloat64Array;
      function isBigInt64Array(value) {
        return whichTypedArray(value) === "BigInt64Array";
      }
      exports.isBigInt64Array = isBigInt64Array;
      function isBigUint64Array(value) {
        return whichTypedArray(value) === "BigUint64Array";
      }
      exports.isBigUint64Array = isBigUint64Array;
      function isMapToString(value) {
        return ObjectToString(value) === "[object Map]";
      }
      isMapToString.working = typeof Map !== "undefined" && isMapToString(/* @__PURE__ */ new Map());
      function isMap(value) {
        if (typeof Map === "undefined") {
          return false;
        }
        return isMapToString.working ? isMapToString(value) : value instanceof Map;
      }
      exports.isMap = isMap;
      function isSetToString(value) {
        return ObjectToString(value) === "[object Set]";
      }
      isSetToString.working = typeof Set !== "undefined" && isSetToString(/* @__PURE__ */ new Set());
      function isSet(value) {
        if (typeof Set === "undefined") {
          return false;
        }
        return isSetToString.working ? isSetToString(value) : value instanceof Set;
      }
      exports.isSet = isSet;
      function isWeakMapToString(value) {
        return ObjectToString(value) === "[object WeakMap]";
      }
      isWeakMapToString.working = typeof WeakMap !== "undefined" && isWeakMapToString(/* @__PURE__ */ new WeakMap());
      function isWeakMap(value) {
        if (typeof WeakMap === "undefined") {
          return false;
        }
        return isWeakMapToString.working ? isWeakMapToString(value) : value instanceof WeakMap;
      }
      exports.isWeakMap = isWeakMap;
      function isWeakSetToString(value) {
        return ObjectToString(value) === "[object WeakSet]";
      }
      isWeakSetToString.working = typeof WeakSet !== "undefined" && isWeakSetToString(/* @__PURE__ */ new WeakSet());
      function isWeakSet(value) {
        return isWeakSetToString(value);
      }
      exports.isWeakSet = isWeakSet;
      function isArrayBufferToString(value) {
        return ObjectToString(value) === "[object ArrayBuffer]";
      }
      isArrayBufferToString.working = typeof ArrayBuffer !== "undefined" && isArrayBufferToString(new ArrayBuffer());
      function isArrayBuffer(value) {
        if (typeof ArrayBuffer === "undefined") {
          return false;
        }
        return isArrayBufferToString.working ? isArrayBufferToString(value) : value instanceof ArrayBuffer;
      }
      exports.isArrayBuffer = isArrayBuffer;
      function isDataViewToString(value) {
        return ObjectToString(value) === "[object DataView]";
      }
      isDataViewToString.working = typeof ArrayBuffer !== "undefined" && typeof DataView !== "undefined" && isDataViewToString(new DataView(new ArrayBuffer(1), 0, 1));
      function isDataView(value) {
        if (typeof DataView === "undefined") {
          return false;
        }
        return isDataViewToString.working ? isDataViewToString(value) : value instanceof DataView;
      }
      exports.isDataView = isDataView;
      var SharedArrayBufferCopy = typeof SharedArrayBuffer !== "undefined" ? SharedArrayBuffer : void 0;
      function isSharedArrayBufferToString(value) {
        return ObjectToString(value) === "[object SharedArrayBuffer]";
      }
      function isSharedArrayBuffer(value) {
        if (typeof SharedArrayBufferCopy === "undefined") {
          return false;
        }
        if (typeof isSharedArrayBufferToString.working === "undefined") {
          isSharedArrayBufferToString.working = isSharedArrayBufferToString(new SharedArrayBufferCopy());
        }
        return isSharedArrayBufferToString.working ? isSharedArrayBufferToString(value) : value instanceof SharedArrayBufferCopy;
      }
      exports.isSharedArrayBuffer = isSharedArrayBuffer;
      function isAsyncFunction(value) {
        return ObjectToString(value) === "[object AsyncFunction]";
      }
      exports.isAsyncFunction = isAsyncFunction;
      function isMapIterator(value) {
        return ObjectToString(value) === "[object Map Iterator]";
      }
      exports.isMapIterator = isMapIterator;
      function isSetIterator(value) {
        return ObjectToString(value) === "[object Set Iterator]";
      }
      exports.isSetIterator = isSetIterator;
      function isGeneratorObject(value) {
        return ObjectToString(value) === "[object Generator]";
      }
      exports.isGeneratorObject = isGeneratorObject;
      function isWebAssemblyCompiledModule(value) {
        return ObjectToString(value) === "[object WebAssembly.Module]";
      }
      exports.isWebAssemblyCompiledModule = isWebAssemblyCompiledModule;
      function isNumberObject(value) {
        return checkBoxedPrimitive(value, numberValue);
      }
      exports.isNumberObject = isNumberObject;
      function isStringObject(value) {
        return checkBoxedPrimitive(value, stringValue);
      }
      exports.isStringObject = isStringObject;
      function isBooleanObject(value) {
        return checkBoxedPrimitive(value, booleanValue);
      }
      exports.isBooleanObject = isBooleanObject;
      function isBigIntObject(value) {
        return BigIntSupported && checkBoxedPrimitive(value, bigIntValue);
      }
      exports.isBigIntObject = isBigIntObject;
      function isSymbolObject(value) {
        return SymbolSupported && checkBoxedPrimitive(value, symbolValue);
      }
      exports.isSymbolObject = isSymbolObject;
      function isBoxedPrimitive(value) {
        return isNumberObject(value) || isStringObject(value) || isBooleanObject(value) || isBigIntObject(value) || isSymbolObject(value);
      }
      exports.isBoxedPrimitive = isBoxedPrimitive;
      function isAnyArrayBuffer(value) {
        return typeof Uint8Array !== "undefined" && (isArrayBuffer(value) || isSharedArrayBuffer(value));
      }
      exports.isAnyArrayBuffer = isAnyArrayBuffer;
      ["isProxy", "isExternal", "isModuleNamespaceObject"].forEach(function(method) {
        Object.defineProperty(exports, method, {
          enumerable: false,
          value: function() {
            throw new Error(method + " is not supported in userland");
          }
        });
      });
    }
  });

  // node_modules/util/support/isBufferBrowser.js
  var require_isBufferBrowser = __commonJS({
    "node_modules/util/support/isBufferBrowser.js"(exports, module) {
      module.exports = function isBuffer(arg) {
        return arg && typeof arg === "object" && typeof arg.copy === "function" && typeof arg.fill === "function" && typeof arg.readUInt8 === "function";
      };
    }
  });

  // node_modules/inherits/inherits_browser.js
  var require_inherits_browser = __commonJS({
    "node_modules/inherits/inherits_browser.js"(exports, module) {
      if (typeof Object.create === "function") {
        module.exports = function inherits(ctor, superCtor) {
          if (superCtor) {
            ctor.super_ = superCtor;
            ctor.prototype = Object.create(superCtor.prototype, {
              constructor: {
                value: ctor,
                enumerable: false,
                writable: true,
                configurable: true
              }
            });
          }
        };
      } else {
        module.exports = function inherits(ctor, superCtor) {
          if (superCtor) {
            ctor.super_ = superCtor;
            var TempCtor = function() {
            };
            TempCtor.prototype = superCtor.prototype;
            ctor.prototype = new TempCtor();
            ctor.prototype.constructor = ctor;
          }
        };
      }
    }
  });

  // node_modules/util/util.js
  var require_util = __commonJS({
    "node_modules/util/util.js"(exports) {
      var getOwnPropertyDescriptors = Object.getOwnPropertyDescriptors || function getOwnPropertyDescriptors2(obj) {
        var keys = Object.keys(obj);
        var descriptors = {};
        for (var i = 0; i < keys.length; i++) {
          descriptors[keys[i]] = Object.getOwnPropertyDescriptor(obj, keys[i]);
        }
        return descriptors;
      };
      var formatRegExp = /%[sdj%]/g;
      exports.format = function(f) {
        if (!isString(f)) {
          var objects = [];
          for (var i = 0; i < arguments.length; i++) {
            objects.push(inspect(arguments[i]));
          }
          return objects.join(" ");
        }
        var i = 1;
        var args = arguments;
        var len = args.length;
        var str = String(f).replace(formatRegExp, function(x2) {
          if (x2 === "%%") return "%";
          if (i >= len) return x2;
          switch (x2) {
            case "%s":
              return String(args[i++]);
            case "%d":
              return Number(args[i++]);
            case "%j":
              try {
                return JSON.stringify(args[i++]);
              } catch (_) {
                return "[Circular]";
              }
            default:
              return x2;
          }
        });
        for (var x = args[i]; i < len; x = args[++i]) {
          if (isNull(x) || !isObject(x)) {
            str += " " + x;
          } else {
            str += " " + inspect(x);
          }
        }
        return str;
      };
      exports.deprecate = function(fn, msg) {
        if (typeof process !== "undefined" && process.noDeprecation === true) {
          return fn;
        }
        if (typeof process === "undefined") {
          return function() {
            return exports.deprecate(fn, msg).apply(this, arguments);
          };
        }
        var warned = false;
        function deprecated() {
          if (!warned) {
            if (process.throwDeprecation) {
              throw new Error(msg);
            } else if (process.traceDeprecation) {
              console.trace(msg);
            } else {
              console.error(msg);
            }
            warned = true;
          }
          return fn.apply(this, arguments);
        }
        return deprecated;
      };
      var debugs = {};
      var debugEnvRegex = /^$/;
      if (process.env.NODE_DEBUG) {
        debugEnv = process.env.NODE_DEBUG;
        debugEnv = debugEnv.replace(/[|\\{}()[\]^$+?.]/g, "\\$&").replace(/\*/g, ".*").replace(/,/g, "$|^").toUpperCase();
        debugEnvRegex = new RegExp("^" + debugEnv + "$", "i");
      }
      var debugEnv;
      exports.debuglog = function(set) {
        set = set.toUpperCase();
        if (!debugs[set]) {
          if (debugEnvRegex.test(set)) {
            var pid = process.pid;
            debugs[set] = function() {
              var msg = exports.format.apply(exports, arguments);
              console.error("%s %d: %s", set, pid, msg);
            };
          } else {
            debugs[set] = function() {
            };
          }
        }
        return debugs[set];
      };
      function inspect(obj, opts) {
        var ctx = {
          seen: [],
          stylize: stylizeNoColor
        };
        if (arguments.length >= 3) ctx.depth = arguments[2];
        if (arguments.length >= 4) ctx.colors = arguments[3];
        if (isBoolean(opts)) {
          ctx.showHidden = opts;
        } else if (opts) {
          exports._extend(ctx, opts);
        }
        if (isUndefined(ctx.showHidden)) ctx.showHidden = false;
        if (isUndefined(ctx.depth)) ctx.depth = 2;
        if (isUndefined(ctx.colors)) ctx.colors = false;
        if (isUndefined(ctx.customInspect)) ctx.customInspect = true;
        if (ctx.colors) ctx.stylize = stylizeWithColor;
        return formatValue(ctx, obj, ctx.depth);
      }
      exports.inspect = inspect;
      inspect.colors = {
        "bold": [1, 22],
        "italic": [3, 23],
        "underline": [4, 24],
        "inverse": [7, 27],
        "white": [37, 39],
        "grey": [90, 39],
        "black": [30, 39],
        "blue": [34, 39],
        "cyan": [36, 39],
        "green": [32, 39],
        "magenta": [35, 39],
        "red": [31, 39],
        "yellow": [33, 39]
      };
      inspect.styles = {
        "special": "cyan",
        "number": "yellow",
        "boolean": "yellow",
        "undefined": "grey",
        "null": "bold",
        "string": "green",
        "date": "magenta",
        // "name": intentionally not styling
        "regexp": "red"
      };
      function stylizeWithColor(str, styleType) {
        var style = inspect.styles[styleType];
        if (style) {
          return "\x1B[" + inspect.colors[style][0] + "m" + str + "\x1B[" + inspect.colors[style][1] + "m";
        } else {
          return str;
        }
      }
      function stylizeNoColor(str, styleType) {
        return str;
      }
      function arrayToHash(array) {
        var hash = {};
        array.forEach(function(val, idx) {
          hash[val] = true;
        });
        return hash;
      }
      function formatValue(ctx, value, recurseTimes) {
        if (ctx.customInspect && value && isFunction(value.inspect) && // Filter out the util module, it's inspect function is special
        value.inspect !== exports.inspect && // Also filter out any prototype objects using the circular check.
        !(value.constructor && value.constructor.prototype === value)) {
          var ret = value.inspect(recurseTimes, ctx);
          if (!isString(ret)) {
            ret = formatValue(ctx, ret, recurseTimes);
          }
          return ret;
        }
        var primitive = formatPrimitive(ctx, value);
        if (primitive) {
          return primitive;
        }
        var keys = Object.keys(value);
        var visibleKeys = arrayToHash(keys);
        if (ctx.showHidden) {
          keys = Object.getOwnPropertyNames(value);
        }
        if (isError(value) && (keys.indexOf("message") >= 0 || keys.indexOf("description") >= 0)) {
          return formatError(value);
        }
        if (keys.length === 0) {
          if (isFunction(value)) {
            var name = value.name ? ": " + value.name : "";
            return ctx.stylize("[Function" + name + "]", "special");
          }
          if (isRegExp(value)) {
            return ctx.stylize(RegExp.prototype.toString.call(value), "regexp");
          }
          if (isDate(value)) {
            return ctx.stylize(Date.prototype.toString.call(value), "date");
          }
          if (isError(value)) {
            return formatError(value);
          }
        }
        var base = "", array = false, braces = ["{", "}"];
        if (isArray(value)) {
          array = true;
          braces = ["[", "]"];
        }
        if (isFunction(value)) {
          var n = value.name ? ": " + value.name : "";
          base = " [Function" + n + "]";
        }
        if (isRegExp(value)) {
          base = " " + RegExp.prototype.toString.call(value);
        }
        if (isDate(value)) {
          base = " " + Date.prototype.toUTCString.call(value);
        }
        if (isError(value)) {
          base = " " + formatError(value);
        }
        if (keys.length === 0 && (!array || value.length == 0)) {
          return braces[0] + base + braces[1];
        }
        if (recurseTimes < 0) {
          if (isRegExp(value)) {
            return ctx.stylize(RegExp.prototype.toString.call(value), "regexp");
          } else {
            return ctx.stylize("[Object]", "special");
          }
        }
        ctx.seen.push(value);
        var output;
        if (array) {
          output = formatArray(ctx, value, recurseTimes, visibleKeys, keys);
        } else {
          output = keys.map(function(key) {
            return formatProperty(ctx, value, recurseTimes, visibleKeys, key, array);
          });
        }
        ctx.seen.pop();
        return reduceToSingleString(output, base, braces);
      }
      function formatPrimitive(ctx, value) {
        if (isUndefined(value))
          return ctx.stylize("undefined", "undefined");
        if (isString(value)) {
          var simple = "'" + JSON.stringify(value).replace(/^"|"$/g, "").replace(/'/g, "\\'").replace(/\\"/g, '"') + "'";
          return ctx.stylize(simple, "string");
        }
        if (isNumber(value))
          return ctx.stylize("" + value, "number");
        if (isBoolean(value))
          return ctx.stylize("" + value, "boolean");
        if (isNull(value))
          return ctx.stylize("null", "null");
      }
      function formatError(value) {
        return "[" + Error.prototype.toString.call(value) + "]";
      }
      function formatArray(ctx, value, recurseTimes, visibleKeys, keys) {
        var output = [];
        for (var i = 0, l = value.length; i < l; ++i) {
          if (hasOwnProperty(value, String(i))) {
            output.push(formatProperty(
              ctx,
              value,
              recurseTimes,
              visibleKeys,
              String(i),
              true
            ));
          } else {
            output.push("");
          }
        }
        keys.forEach(function(key) {
          if (!key.match(/^\d+$/)) {
            output.push(formatProperty(
              ctx,
              value,
              recurseTimes,
              visibleKeys,
              key,
              true
            ));
          }
        });
        return output;
      }
      function formatProperty(ctx, value, recurseTimes, visibleKeys, key, array) {
        var name, str, desc;
        desc = Object.getOwnPropertyDescriptor(value, key) || { value: value[key] };
        if (desc.get) {
          if (desc.set) {
            str = ctx.stylize("[Getter/Setter]", "special");
          } else {
            str = ctx.stylize("[Getter]", "special");
          }
        } else {
          if (desc.set) {
            str = ctx.stylize("[Setter]", "special");
          }
        }
        if (!hasOwnProperty(visibleKeys, key)) {
          name = "[" + key + "]";
        }
        if (!str) {
          if (ctx.seen.indexOf(desc.value) < 0) {
            if (isNull(recurseTimes)) {
              str = formatValue(ctx, desc.value, null);
            } else {
              str = formatValue(ctx, desc.value, recurseTimes - 1);
            }
            if (str.indexOf("\n") > -1) {
              if (array) {
                str = str.split("\n").map(function(line) {
                  return "  " + line;
                }).join("\n").slice(2);
              } else {
                str = "\n" + str.split("\n").map(function(line) {
                  return "   " + line;
                }).join("\n");
              }
            }
          } else {
            str = ctx.stylize("[Circular]", "special");
          }
        }
        if (isUndefined(name)) {
          if (array && key.match(/^\d+$/)) {
            return str;
          }
          name = JSON.stringify("" + key);
          if (name.match(/^"([a-zA-Z_][a-zA-Z_0-9]*)"$/)) {
            name = name.slice(1, -1);
            name = ctx.stylize(name, "name");
          } else {
            name = name.replace(/'/g, "\\'").replace(/\\"/g, '"').replace(/(^"|"$)/g, "'");
            name = ctx.stylize(name, "string");
          }
        }
        return name + ": " + str;
      }
      function reduceToSingleString(output, base, braces) {
        var numLinesEst = 0;
        var length = output.reduce(function(prev, cur) {
          numLinesEst++;
          if (cur.indexOf("\n") >= 0) numLinesEst++;
          return prev + cur.replace(/\u001b\[\d\d?m/g, "").length + 1;
        }, 0);
        if (length > 60) {
          return braces[0] + (base === "" ? "" : base + "\n ") + " " + output.join(",\n  ") + " " + braces[1];
        }
        return braces[0] + base + " " + output.join(", ") + " " + braces[1];
      }
      exports.types = require_types();
      function isArray(ar) {
        return Array.isArray(ar);
      }
      exports.isArray = isArray;
      function isBoolean(arg) {
        return typeof arg === "boolean";
      }
      exports.isBoolean = isBoolean;
      function isNull(arg) {
        return arg === null;
      }
      exports.isNull = isNull;
      function isNullOrUndefined(arg) {
        return arg == null;
      }
      exports.isNullOrUndefined = isNullOrUndefined;
      function isNumber(arg) {
        return typeof arg === "number";
      }
      exports.isNumber = isNumber;
      function isString(arg) {
        return typeof arg === "string";
      }
      exports.isString = isString;
      function isSymbol(arg) {
        return typeof arg === "symbol";
      }
      exports.isSymbol = isSymbol;
      function isUndefined(arg) {
        return arg === void 0;
      }
      exports.isUndefined = isUndefined;
      function isRegExp(re) {
        return isObject(re) && objectToString(re) === "[object RegExp]";
      }
      exports.isRegExp = isRegExp;
      exports.types.isRegExp = isRegExp;
      function isObject(arg) {
        return typeof arg === "object" && arg !== null;
      }
      exports.isObject = isObject;
      function isDate(d) {
        return isObject(d) && objectToString(d) === "[object Date]";
      }
      exports.isDate = isDate;
      exports.types.isDate = isDate;
      function isError(e) {
        return isObject(e) && (objectToString(e) === "[object Error]" || e instanceof Error);
      }
      exports.isError = isError;
      exports.types.isNativeError = isError;
      function isFunction(arg) {
        return typeof arg === "function";
      }
      exports.isFunction = isFunction;
      function isPrimitive(arg) {
        return arg === null || typeof arg === "boolean" || typeof arg === "number" || typeof arg === "string" || typeof arg === "symbol" || // ES6 symbol
        typeof arg === "undefined";
      }
      exports.isPrimitive = isPrimitive;
      exports.isBuffer = require_isBufferBrowser();
      function objectToString(o) {
        return Object.prototype.toString.call(o);
      }
      function pad(n) {
        return n < 10 ? "0" + n.toString(10) : n.toString(10);
      }
      var months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec"
      ];
      function timestamp() {
        var d = /* @__PURE__ */ new Date();
        var time = [
          pad(d.getHours()),
          pad(d.getMinutes()),
          pad(d.getSeconds())
        ].join(":");
        return [d.getDate(), months[d.getMonth()], time].join(" ");
      }
      exports.log = function() {
        console.log("%s - %s", timestamp(), exports.format.apply(exports, arguments));
      };
      exports.inherits = require_inherits_browser();
      exports._extend = function(origin, add) {
        if (!add || !isObject(add)) return origin;
        var keys = Object.keys(add);
        var i = keys.length;
        while (i--) {
          origin[keys[i]] = add[keys[i]];
        }
        return origin;
      };
      function hasOwnProperty(obj, prop) {
        return Object.prototype.hasOwnProperty.call(obj, prop);
      }
      var kCustomPromisifiedSymbol = typeof Symbol !== "undefined" ? /* @__PURE__ */ Symbol("util.promisify.custom") : void 0;
      exports.promisify = function promisify(original) {
        if (typeof original !== "function")
          throw new TypeError('The "original" argument must be of type Function');
        if (kCustomPromisifiedSymbol && original[kCustomPromisifiedSymbol]) {
          var fn = original[kCustomPromisifiedSymbol];
          if (typeof fn !== "function") {
            throw new TypeError('The "util.promisify.custom" argument must be of type Function');
          }
          Object.defineProperty(fn, kCustomPromisifiedSymbol, {
            value: fn,
            enumerable: false,
            writable: false,
            configurable: true
          });
          return fn;
        }
        function fn() {
          var promiseResolve, promiseReject;
          var promise = new Promise(function(resolve, reject) {
            promiseResolve = resolve;
            promiseReject = reject;
          });
          var args = [];
          for (var i = 0; i < arguments.length; i++) {
            args.push(arguments[i]);
          }
          args.push(function(err, value) {
            if (err) {
              promiseReject(err);
            } else {
              promiseResolve(value);
            }
          });
          try {
            original.apply(this, args);
          } catch (err) {
            promiseReject(err);
          }
          return promise;
        }
        Object.setPrototypeOf(fn, Object.getPrototypeOf(original));
        if (kCustomPromisifiedSymbol) Object.defineProperty(fn, kCustomPromisifiedSymbol, {
          value: fn,
          enumerable: false,
          writable: false,
          configurable: true
        });
        return Object.defineProperties(
          fn,
          getOwnPropertyDescriptors(original)
        );
      };
      exports.promisify.custom = kCustomPromisifiedSymbol;
      function callbackifyOnRejected(reason, cb) {
        if (!reason) {
          var newReason = new Error("Promise was rejected with a falsy value");
          newReason.reason = reason;
          reason = newReason;
        }
        return cb(reason);
      }
      function callbackify(original) {
        if (typeof original !== "function") {
          throw new TypeError('The "original" argument must be of type Function');
        }
        function callbackified() {
          var args = [];
          for (var i = 0; i < arguments.length; i++) {
            args.push(arguments[i]);
          }
          var maybeCb = args.pop();
          if (typeof maybeCb !== "function") {
            throw new TypeError("The last argument must be of type Function");
          }
          var self = this;
          var cb = function() {
            return maybeCb.apply(self, arguments);
          };
          original.apply(this, args).then(
            function(ret) {
              process.nextTick(cb.bind(null, null, ret));
            },
            function(rej) {
              process.nextTick(callbackifyOnRejected.bind(null, rej, cb));
            }
          );
        }
        Object.setPrototypeOf(callbackified, Object.getPrototypeOf(original));
        Object.defineProperties(
          callbackified,
          getOwnPropertyDescriptors(original)
        );
        return callbackified;
      }
      exports.callbackify = callbackify;
    }
  });

  // node_modules/assert/build/internal/errors.js
  var require_errors = __commonJS({
    "node_modules/assert/build/internal/errors.js"(exports, module) {
      "use strict";
      function _typeof(o) {
        "@babel/helpers - typeof";
        return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o2) {
          return typeof o2;
        } : function(o2) {
          return o2 && "function" == typeof Symbol && o2.constructor === Symbol && o2 !== Symbol.prototype ? "symbol" : typeof o2;
        }, _typeof(o);
      }
      function _defineProperties(target, props) {
        for (var i = 0; i < props.length; i++) {
          var descriptor = props[i];
          descriptor.enumerable = descriptor.enumerable || false;
          descriptor.configurable = true;
          if ("value" in descriptor) descriptor.writable = true;
          Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
        }
      }
      function _createClass(Constructor, protoProps, staticProps) {
        if (protoProps) _defineProperties(Constructor.prototype, protoProps);
        if (staticProps) _defineProperties(Constructor, staticProps);
        Object.defineProperty(Constructor, "prototype", { writable: false });
        return Constructor;
      }
      function _toPropertyKey(arg) {
        var key = _toPrimitive(arg, "string");
        return _typeof(key) === "symbol" ? key : String(key);
      }
      function _toPrimitive(input, hint) {
        if (_typeof(input) !== "object" || input === null) return input;
        var prim = input[Symbol.toPrimitive];
        if (prim !== void 0) {
          var res = prim.call(input, hint || "default");
          if (_typeof(res) !== "object") return res;
          throw new TypeError("@@toPrimitive must return a primitive value.");
        }
        return (hint === "string" ? String : Number)(input);
      }
      function _classCallCheck(instance, Constructor) {
        if (!(instance instanceof Constructor)) {
          throw new TypeError("Cannot call a class as a function");
        }
      }
      function _inherits(subClass, superClass) {
        if (typeof superClass !== "function" && superClass !== null) {
          throw new TypeError("Super expression must either be null or a function");
        }
        subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, writable: true, configurable: true } });
        Object.defineProperty(subClass, "prototype", { writable: false });
        if (superClass) _setPrototypeOf(subClass, superClass);
      }
      function _setPrototypeOf(o, p) {
        _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf2(o2, p2) {
          o2.__proto__ = p2;
          return o2;
        };
        return _setPrototypeOf(o, p);
      }
      function _createSuper(Derived) {
        var hasNativeReflectConstruct = _isNativeReflectConstruct();
        return function _createSuperInternal() {
          var Super = _getPrototypeOf(Derived), result;
          if (hasNativeReflectConstruct) {
            var NewTarget = _getPrototypeOf(this).constructor;
            result = Reflect.construct(Super, arguments, NewTarget);
          } else {
            result = Super.apply(this, arguments);
          }
          return _possibleConstructorReturn(this, result);
        };
      }
      function _possibleConstructorReturn(self, call) {
        if (call && (_typeof(call) === "object" || typeof call === "function")) {
          return call;
        } else if (call !== void 0) {
          throw new TypeError("Derived constructors may only return object or undefined");
        }
        return _assertThisInitialized(self);
      }
      function _assertThisInitialized(self) {
        if (self === void 0) {
          throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
        }
        return self;
      }
      function _isNativeReflectConstruct() {
        if (typeof Reflect === "undefined" || !Reflect.construct) return false;
        if (Reflect.construct.sham) return false;
        if (typeof Proxy === "function") return true;
        try {
          Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {
          }));
          return true;
        } catch (e) {
          return false;
        }
      }
      function _getPrototypeOf(o) {
        _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf2(o2) {
          return o2.__proto__ || Object.getPrototypeOf(o2);
        };
        return _getPrototypeOf(o);
      }
      var codes = {};
      var assert;
      var util;
      function createErrorType(code, message, Base) {
        if (!Base) {
          Base = Error;
        }
        function getMessage(arg1, arg2, arg3) {
          if (typeof message === "string") {
            return message;
          } else {
            return message(arg1, arg2, arg3);
          }
        }
        var NodeError = /* @__PURE__ */ (function(_Base) {
          _inherits(NodeError2, _Base);
          var _super = _createSuper(NodeError2);
          function NodeError2(arg1, arg2, arg3) {
            var _this;
            _classCallCheck(this, NodeError2);
            _this = _super.call(this, getMessage(arg1, arg2, arg3));
            _this.code = code;
            return _this;
          }
          return _createClass(NodeError2);
        })(Base);
        codes[code] = NodeError;
      }
      function oneOf(expected, thing) {
        if (Array.isArray(expected)) {
          var len = expected.length;
          expected = expected.map(function(i) {
            return String(i);
          });
          if (len > 2) {
            return "one of ".concat(thing, " ").concat(expected.slice(0, len - 1).join(", "), ", or ") + expected[len - 1];
          } else if (len === 2) {
            return "one of ".concat(thing, " ").concat(expected[0], " or ").concat(expected[1]);
          } else {
            return "of ".concat(thing, " ").concat(expected[0]);
          }
        } else {
          return "of ".concat(thing, " ").concat(String(expected));
        }
      }
      function startsWith(str, search, pos) {
        return str.substr(!pos || pos < 0 ? 0 : +pos, search.length) === search;
      }
      function endsWith(str, search, this_len) {
        if (this_len === void 0 || this_len > str.length) {
          this_len = str.length;
        }
        return str.substring(this_len - search.length, this_len) === search;
      }
      function includes(str, search, start) {
        if (typeof start !== "number") {
          start = 0;
        }
        if (start + search.length > str.length) {
          return false;
        } else {
          return str.indexOf(search, start) !== -1;
        }
      }
      createErrorType("ERR_AMBIGUOUS_ARGUMENT", 'The "%s" argument is ambiguous. %s', TypeError);
      createErrorType("ERR_INVALID_ARG_TYPE", function(name, expected, actual) {
        if (assert === void 0) assert = require_assert();
        assert(typeof name === "string", "'name' must be a string");
        var determiner;
        if (typeof expected === "string" && startsWith(expected, "not ")) {
          determiner = "must not be";
          expected = expected.replace(/^not /, "");
        } else {
          determiner = "must be";
        }
        var msg;
        if (endsWith(name, " argument")) {
          msg = "The ".concat(name, " ").concat(determiner, " ").concat(oneOf(expected, "type"));
        } else {
          var type = includes(name, ".") ? "property" : "argument";
          msg = 'The "'.concat(name, '" ').concat(type, " ").concat(determiner, " ").concat(oneOf(expected, "type"));
        }
        msg += ". Received type ".concat(_typeof(actual));
        return msg;
      }, TypeError);
      createErrorType("ERR_INVALID_ARG_VALUE", function(name, value) {
        var reason = arguments.length > 2 && arguments[2] !== void 0 ? arguments[2] : "is invalid";
        if (util === void 0) util = require_util();
        var inspected = util.inspect(value);
        if (inspected.length > 128) {
          inspected = "".concat(inspected.slice(0, 128), "...");
        }
        return "The argument '".concat(name, "' ").concat(reason, ". Received ").concat(inspected);
      }, TypeError, RangeError);
      createErrorType("ERR_INVALID_RETURN_VALUE", function(input, name, value) {
        var type;
        if (value && value.constructor && value.constructor.name) {
          type = "instance of ".concat(value.constructor.name);
        } else {
          type = "type ".concat(_typeof(value));
        }
        return "Expected ".concat(input, ' to be returned from the "').concat(name, '"') + " function but got ".concat(type, ".");
      }, TypeError);
      createErrorType("ERR_MISSING_ARGS", function() {
        for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
          args[_key] = arguments[_key];
        }
        if (assert === void 0) assert = require_assert();
        assert(args.length > 0, "At least one arg needs to be specified");
        var msg = "The ";
        var len = args.length;
        args = args.map(function(a) {
          return '"'.concat(a, '"');
        });
        switch (len) {
          case 1:
            msg += "".concat(args[0], " argument");
            break;
          case 2:
            msg += "".concat(args[0], " and ").concat(args[1], " arguments");
            break;
          default:
            msg += args.slice(0, len - 1).join(", ");
            msg += ", and ".concat(args[len - 1], " arguments");
            break;
        }
        return "".concat(msg, " must be specified");
      }, TypeError);
      module.exports.codes = codes;
    }
  });

  // node_modules/assert/build/internal/assert/assertion_error.js
  var require_assertion_error = __commonJS({
    "node_modules/assert/build/internal/assert/assertion_error.js"(exports, module) {
      "use strict";
      function ownKeys(e, r) {
        var t = Object.keys(e);
        if (Object.getOwnPropertySymbols) {
          var o = Object.getOwnPropertySymbols(e);
          r && (o = o.filter(function(r2) {
            return Object.getOwnPropertyDescriptor(e, r2).enumerable;
          })), t.push.apply(t, o);
        }
        return t;
      }
      function _objectSpread(e) {
        for (var r = 1; r < arguments.length; r++) {
          var t = null != arguments[r] ? arguments[r] : {};
          r % 2 ? ownKeys(Object(t), true).forEach(function(r2) {
            _defineProperty(e, r2, t[r2]);
          }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r2) {
            Object.defineProperty(e, r2, Object.getOwnPropertyDescriptor(t, r2));
          });
        }
        return e;
      }
      function _defineProperty(obj, key, value) {
        key = _toPropertyKey(key);
        if (key in obj) {
          Object.defineProperty(obj, key, { value, enumerable: true, configurable: true, writable: true });
        } else {
          obj[key] = value;
        }
        return obj;
      }
      function _classCallCheck(instance, Constructor) {
        if (!(instance instanceof Constructor)) {
          throw new TypeError("Cannot call a class as a function");
        }
      }
      function _defineProperties(target, props) {
        for (var i = 0; i < props.length; i++) {
          var descriptor = props[i];
          descriptor.enumerable = descriptor.enumerable || false;
          descriptor.configurable = true;
          if ("value" in descriptor) descriptor.writable = true;
          Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
        }
      }
      function _createClass(Constructor, protoProps, staticProps) {
        if (protoProps) _defineProperties(Constructor.prototype, protoProps);
        if (staticProps) _defineProperties(Constructor, staticProps);
        Object.defineProperty(Constructor, "prototype", { writable: false });
        return Constructor;
      }
      function _toPropertyKey(arg) {
        var key = _toPrimitive(arg, "string");
        return _typeof(key) === "symbol" ? key : String(key);
      }
      function _toPrimitive(input, hint) {
        if (_typeof(input) !== "object" || input === null) return input;
        var prim = input[Symbol.toPrimitive];
        if (prim !== void 0) {
          var res = prim.call(input, hint || "default");
          if (_typeof(res) !== "object") return res;
          throw new TypeError("@@toPrimitive must return a primitive value.");
        }
        return (hint === "string" ? String : Number)(input);
      }
      function _inherits(subClass, superClass) {
        if (typeof superClass !== "function" && superClass !== null) {
          throw new TypeError("Super expression must either be null or a function");
        }
        subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, writable: true, configurable: true } });
        Object.defineProperty(subClass, "prototype", { writable: false });
        if (superClass) _setPrototypeOf(subClass, superClass);
      }
      function _createSuper(Derived) {
        var hasNativeReflectConstruct = _isNativeReflectConstruct();
        return function _createSuperInternal() {
          var Super = _getPrototypeOf(Derived), result;
          if (hasNativeReflectConstruct) {
            var NewTarget = _getPrototypeOf(this).constructor;
            result = Reflect.construct(Super, arguments, NewTarget);
          } else {
            result = Super.apply(this, arguments);
          }
          return _possibleConstructorReturn(this, result);
        };
      }
      function _possibleConstructorReturn(self, call) {
        if (call && (_typeof(call) === "object" || typeof call === "function")) {
          return call;
        } else if (call !== void 0) {
          throw new TypeError("Derived constructors may only return object or undefined");
        }
        return _assertThisInitialized(self);
      }
      function _assertThisInitialized(self) {
        if (self === void 0) {
          throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
        }
        return self;
      }
      function _wrapNativeSuper(Class) {
        var _cache = typeof Map === "function" ? /* @__PURE__ */ new Map() : void 0;
        _wrapNativeSuper = function _wrapNativeSuper2(Class2) {
          if (Class2 === null || !_isNativeFunction(Class2)) return Class2;
          if (typeof Class2 !== "function") {
            throw new TypeError("Super expression must either be null or a function");
          }
          if (typeof _cache !== "undefined") {
            if (_cache.has(Class2)) return _cache.get(Class2);
            _cache.set(Class2, Wrapper);
          }
          function Wrapper() {
            return _construct(Class2, arguments, _getPrototypeOf(this).constructor);
          }
          Wrapper.prototype = Object.create(Class2.prototype, { constructor: { value: Wrapper, enumerable: false, writable: true, configurable: true } });
          return _setPrototypeOf(Wrapper, Class2);
        };
        return _wrapNativeSuper(Class);
      }
      function _construct(Parent, args, Class) {
        if (_isNativeReflectConstruct()) {
          _construct = Reflect.construct.bind();
        } else {
          _construct = function _construct2(Parent2, args2, Class2) {
            var a = [null];
            a.push.apply(a, args2);
            var Constructor = Function.bind.apply(Parent2, a);
            var instance = new Constructor();
            if (Class2) _setPrototypeOf(instance, Class2.prototype);
            return instance;
          };
        }
        return _construct.apply(null, arguments);
      }
      function _isNativeReflectConstruct() {
        if (typeof Reflect === "undefined" || !Reflect.construct) return false;
        if (Reflect.construct.sham) return false;
        if (typeof Proxy === "function") return true;
        try {
          Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {
          }));
          return true;
        } catch (e) {
          return false;
        }
      }
      function _isNativeFunction(fn) {
        return Function.toString.call(fn).indexOf("[native code]") !== -1;
      }
      function _setPrototypeOf(o, p) {
        _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf2(o2, p2) {
          o2.__proto__ = p2;
          return o2;
        };
        return _setPrototypeOf(o, p);
      }
      function _getPrototypeOf(o) {
        _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf2(o2) {
          return o2.__proto__ || Object.getPrototypeOf(o2);
        };
        return _getPrototypeOf(o);
      }
      function _typeof(o) {
        "@babel/helpers - typeof";
        return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o2) {
          return typeof o2;
        } : function(o2) {
          return o2 && "function" == typeof Symbol && o2.constructor === Symbol && o2 !== Symbol.prototype ? "symbol" : typeof o2;
        }, _typeof(o);
      }
      var _require = require_util();
      var inspect = _require.inspect;
      var _require2 = require_errors();
      var ERR_INVALID_ARG_TYPE = _require2.codes.ERR_INVALID_ARG_TYPE;
      function endsWith(str, search, this_len) {
        if (this_len === void 0 || this_len > str.length) {
          this_len = str.length;
        }
        return str.substring(this_len - search.length, this_len) === search;
      }
      function repeat(str, count) {
        count = Math.floor(count);
        if (str.length == 0 || count == 0) return "";
        var maxCount = str.length * count;
        count = Math.floor(Math.log(count) / Math.log(2));
        while (count) {
          str += str;
          count--;
        }
        str += str.substring(0, maxCount - str.length);
        return str;
      }
      var blue = "";
      var green = "";
      var red = "";
      var white = "";
      var kReadableOperator = {
        deepStrictEqual: "Expected values to be strictly deep-equal:",
        strictEqual: "Expected values to be strictly equal:",
        strictEqualObject: 'Expected "actual" to be reference-equal to "expected":',
        deepEqual: "Expected values to be loosely deep-equal:",
        equal: "Expected values to be loosely equal:",
        notDeepStrictEqual: 'Expected "actual" not to be strictly deep-equal to:',
        notStrictEqual: 'Expected "actual" to be strictly unequal to:',
        notStrictEqualObject: 'Expected "actual" not to be reference-equal to "expected":',
        notDeepEqual: 'Expected "actual" not to be loosely deep-equal to:',
        notEqual: 'Expected "actual" to be loosely unequal to:',
        notIdentical: "Values identical but not reference-equal:"
      };
      var kMaxShortLength = 10;
      function copyError(source) {
        var keys = Object.keys(source);
        var target = Object.create(Object.getPrototypeOf(source));
        keys.forEach(function(key) {
          target[key] = source[key];
        });
        Object.defineProperty(target, "message", {
          value: source.message
        });
        return target;
      }
      function inspectValue(val) {
        return inspect(val, {
          compact: false,
          customInspect: false,
          depth: 1e3,
          maxArrayLength: Infinity,
          // Assert compares only enumerable properties (with a few exceptions).
          showHidden: false,
          // Having a long line as error is better than wrapping the line for
          // comparison for now.
          // TODO(BridgeAR): `breakLength` should be limited as soon as soon as we
          // have meta information about the inspected properties (i.e., know where
          // in what line the property starts and ends).
          breakLength: Infinity,
          // Assert does not detect proxies currently.
          showProxy: false,
          sorted: true,
          // Inspect getters as we also check them when comparing entries.
          getters: true
        });
      }
      function createErrDiff(actual, expected, operator) {
        var other = "";
        var res = "";
        var lastPos = 0;
        var end = "";
        var skipped = false;
        var actualInspected = inspectValue(actual);
        var actualLines = actualInspected.split("\n");
        var expectedLines = inspectValue(expected).split("\n");
        var i = 0;
        var indicator = "";
        if (operator === "strictEqual" && _typeof(actual) === "object" && _typeof(expected) === "object" && actual !== null && expected !== null) {
          operator = "strictEqualObject";
        }
        if (actualLines.length === 1 && expectedLines.length === 1 && actualLines[0] !== expectedLines[0]) {
          var inputLength = actualLines[0].length + expectedLines[0].length;
          if (inputLength <= kMaxShortLength) {
            if ((_typeof(actual) !== "object" || actual === null) && (_typeof(expected) !== "object" || expected === null) && (actual !== 0 || expected !== 0)) {
              return "".concat(kReadableOperator[operator], "\n\n") + "".concat(actualLines[0], " !== ").concat(expectedLines[0], "\n");
            }
          } else if (operator !== "strictEqualObject") {
            var maxLength = process.stderr && process.stderr.isTTY ? process.stderr.columns : 80;
            if (inputLength < maxLength) {
              while (actualLines[0][i] === expectedLines[0][i]) {
                i++;
              }
              if (i > 2) {
                indicator = "\n  ".concat(repeat(" ", i), "^");
                i = 0;
              }
            }
          }
        }
        var a = actualLines[actualLines.length - 1];
        var b = expectedLines[expectedLines.length - 1];
        while (a === b) {
          if (i++ < 2) {
            end = "\n  ".concat(a).concat(end);
          } else {
            other = a;
          }
          actualLines.pop();
          expectedLines.pop();
          if (actualLines.length === 0 || expectedLines.length === 0) break;
          a = actualLines[actualLines.length - 1];
          b = expectedLines[expectedLines.length - 1];
        }
        var maxLines = Math.max(actualLines.length, expectedLines.length);
        if (maxLines === 0) {
          var _actualLines = actualInspected.split("\n");
          if (_actualLines.length > 30) {
            _actualLines[26] = "".concat(blue, "...").concat(white);
            while (_actualLines.length > 27) {
              _actualLines.pop();
            }
          }
          return "".concat(kReadableOperator.notIdentical, "\n\n").concat(_actualLines.join("\n"), "\n");
        }
        if (i > 3) {
          end = "\n".concat(blue, "...").concat(white).concat(end);
          skipped = true;
        }
        if (other !== "") {
          end = "\n  ".concat(other).concat(end);
          other = "";
        }
        var printedLines = 0;
        var msg = kReadableOperator[operator] + "\n".concat(green, "+ actual").concat(white, " ").concat(red, "- expected").concat(white);
        var skippedMsg = " ".concat(blue, "...").concat(white, " Lines skipped");
        for (i = 0; i < maxLines; i++) {
          var cur = i - lastPos;
          if (actualLines.length < i + 1) {
            if (cur > 1 && i > 2) {
              if (cur > 4) {
                res += "\n".concat(blue, "...").concat(white);
                skipped = true;
              } else if (cur > 3) {
                res += "\n  ".concat(expectedLines[i - 2]);
                printedLines++;
              }
              res += "\n  ".concat(expectedLines[i - 1]);
              printedLines++;
            }
            lastPos = i;
            other += "\n".concat(red, "-").concat(white, " ").concat(expectedLines[i]);
            printedLines++;
          } else if (expectedLines.length < i + 1) {
            if (cur > 1 && i > 2) {
              if (cur > 4) {
                res += "\n".concat(blue, "...").concat(white);
                skipped = true;
              } else if (cur > 3) {
                res += "\n  ".concat(actualLines[i - 2]);
                printedLines++;
              }
              res += "\n  ".concat(actualLines[i - 1]);
              printedLines++;
            }
            lastPos = i;
            res += "\n".concat(green, "+").concat(white, " ").concat(actualLines[i]);
            printedLines++;
          } else {
            var expectedLine = expectedLines[i];
            var actualLine = actualLines[i];
            var divergingLines = actualLine !== expectedLine && (!endsWith(actualLine, ",") || actualLine.slice(0, -1) !== expectedLine);
            if (divergingLines && endsWith(expectedLine, ",") && expectedLine.slice(0, -1) === actualLine) {
              divergingLines = false;
              actualLine += ",";
            }
            if (divergingLines) {
              if (cur > 1 && i > 2) {
                if (cur > 4) {
                  res += "\n".concat(blue, "...").concat(white);
                  skipped = true;
                } else if (cur > 3) {
                  res += "\n  ".concat(actualLines[i - 2]);
                  printedLines++;
                }
                res += "\n  ".concat(actualLines[i - 1]);
                printedLines++;
              }
              lastPos = i;
              res += "\n".concat(green, "+").concat(white, " ").concat(actualLine);
              other += "\n".concat(red, "-").concat(white, " ").concat(expectedLine);
              printedLines += 2;
            } else {
              res += other;
              other = "";
              if (cur === 1 || i === 0) {
                res += "\n  ".concat(actualLine);
                printedLines++;
              }
            }
          }
          if (printedLines > 20 && i < maxLines - 2) {
            return "".concat(msg).concat(skippedMsg, "\n").concat(res, "\n").concat(blue, "...").concat(white).concat(other, "\n") + "".concat(blue, "...").concat(white);
          }
        }
        return "".concat(msg).concat(skipped ? skippedMsg : "", "\n").concat(res).concat(other).concat(end).concat(indicator);
      }
      var AssertionError = /* @__PURE__ */ (function(_Error, _inspect$custom) {
        _inherits(AssertionError2, _Error);
        var _super = _createSuper(AssertionError2);
        function AssertionError2(options) {
          var _this;
          _classCallCheck(this, AssertionError2);
          if (_typeof(options) !== "object" || options === null) {
            throw new ERR_INVALID_ARG_TYPE("options", "Object", options);
          }
          var message = options.message, operator = options.operator, stackStartFn = options.stackStartFn;
          var actual = options.actual, expected = options.expected;
          var limit = Error.stackTraceLimit;
          Error.stackTraceLimit = 0;
          if (message != null) {
            _this = _super.call(this, String(message));
          } else {
            if (process.stderr && process.stderr.isTTY) {
              if (process.stderr && process.stderr.getColorDepth && process.stderr.getColorDepth() !== 1) {
                blue = "\x1B[34m";
                green = "\x1B[32m";
                white = "\x1B[39m";
                red = "\x1B[31m";
              } else {
                blue = "";
                green = "";
                white = "";
                red = "";
              }
            }
            if (_typeof(actual) === "object" && actual !== null && _typeof(expected) === "object" && expected !== null && "stack" in actual && actual instanceof Error && "stack" in expected && expected instanceof Error) {
              actual = copyError(actual);
              expected = copyError(expected);
            }
            if (operator === "deepStrictEqual" || operator === "strictEqual") {
              _this = _super.call(this, createErrDiff(actual, expected, operator));
            } else if (operator === "notDeepStrictEqual" || operator === "notStrictEqual") {
              var base = kReadableOperator[operator];
              var res = inspectValue(actual).split("\n");
              if (operator === "notStrictEqual" && _typeof(actual) === "object" && actual !== null) {
                base = kReadableOperator.notStrictEqualObject;
              }
              if (res.length > 30) {
                res[26] = "".concat(blue, "...").concat(white);
                while (res.length > 27) {
                  res.pop();
                }
              }
              if (res.length === 1) {
                _this = _super.call(this, "".concat(base, " ").concat(res[0]));
              } else {
                _this = _super.call(this, "".concat(base, "\n\n").concat(res.join("\n"), "\n"));
              }
            } else {
              var _res = inspectValue(actual);
              var other = "";
              var knownOperators = kReadableOperator[operator];
              if (operator === "notDeepEqual" || operator === "notEqual") {
                _res = "".concat(kReadableOperator[operator], "\n\n").concat(_res);
                if (_res.length > 1024) {
                  _res = "".concat(_res.slice(0, 1021), "...");
                }
              } else {
                other = "".concat(inspectValue(expected));
                if (_res.length > 512) {
                  _res = "".concat(_res.slice(0, 509), "...");
                }
                if (other.length > 512) {
                  other = "".concat(other.slice(0, 509), "...");
                }
                if (operator === "deepEqual" || operator === "equal") {
                  _res = "".concat(knownOperators, "\n\n").concat(_res, "\n\nshould equal\n\n");
                } else {
                  other = " ".concat(operator, " ").concat(other);
                }
              }
              _this = _super.call(this, "".concat(_res).concat(other));
            }
          }
          Error.stackTraceLimit = limit;
          _this.generatedMessage = !message;
          Object.defineProperty(_assertThisInitialized(_this), "name", {
            value: "AssertionError [ERR_ASSERTION]",
            enumerable: false,
            writable: true,
            configurable: true
          });
          _this.code = "ERR_ASSERTION";
          _this.actual = actual;
          _this.expected = expected;
          _this.operator = operator;
          if (Error.captureStackTrace) {
            Error.captureStackTrace(_assertThisInitialized(_this), stackStartFn);
          }
          _this.stack;
          _this.name = "AssertionError";
          return _possibleConstructorReturn(_this);
        }
        _createClass(AssertionError2, [{
          key: "toString",
          value: function toString() {
            return "".concat(this.name, " [").concat(this.code, "]: ").concat(this.message);
          }
        }, {
          key: _inspect$custom,
          value: function value(recurseTimes, ctx) {
            return inspect(this, _objectSpread(_objectSpread({}, ctx), {}, {
              customInspect: false,
              depth: 0
            }));
          }
        }]);
        return AssertionError2;
      })(/* @__PURE__ */ _wrapNativeSuper(Error), inspect.custom);
      module.exports = AssertionError;
    }
  });

  // node_modules/object-keys/isArguments.js
  var require_isArguments = __commonJS({
    "node_modules/object-keys/isArguments.js"(exports, module) {
      "use strict";
      var toStr = Object.prototype.toString;
      module.exports = function isArguments(value) {
        var str = toStr.call(value);
        var isArgs = str === "[object Arguments]";
        if (!isArgs) {
          isArgs = str !== "[object Array]" && value !== null && typeof value === "object" && typeof value.length === "number" && value.length >= 0 && toStr.call(value.callee) === "[object Function]";
        }
        return isArgs;
      };
    }
  });

  // node_modules/object-keys/implementation.js
  var require_implementation2 = __commonJS({
    "node_modules/object-keys/implementation.js"(exports, module) {
      "use strict";
      var keysShim;
      if (!Object.keys) {
        has = Object.prototype.hasOwnProperty;
        toStr = Object.prototype.toString;
        isArgs = require_isArguments();
        isEnumerable = Object.prototype.propertyIsEnumerable;
        hasDontEnumBug = !isEnumerable.call({ toString: null }, "toString");
        hasProtoEnumBug = isEnumerable.call(function() {
        }, "prototype");
        dontEnums = [
          "toString",
          "toLocaleString",
          "valueOf",
          "hasOwnProperty",
          "isPrototypeOf",
          "propertyIsEnumerable",
          "constructor"
        ];
        equalsConstructorPrototype = function(o) {
          var ctor = o.constructor;
          return ctor && ctor.prototype === o;
        };
        excludedKeys = {
          $applicationCache: true,
          $console: true,
          $external: true,
          $frame: true,
          $frameElement: true,
          $frames: true,
          $innerHeight: true,
          $innerWidth: true,
          $onmozfullscreenchange: true,
          $onmozfullscreenerror: true,
          $outerHeight: true,
          $outerWidth: true,
          $pageXOffset: true,
          $pageYOffset: true,
          $parent: true,
          $scrollLeft: true,
          $scrollTop: true,
          $scrollX: true,
          $scrollY: true,
          $self: true,
          $webkitIndexedDB: true,
          $webkitStorageInfo: true,
          $window: true
        };
        hasAutomationEqualityBug = (function() {
          if (typeof window === "undefined") {
            return false;
          }
          for (var k in window) {
            try {
              if (!excludedKeys["$" + k] && has.call(window, k) && window[k] !== null && typeof window[k] === "object") {
                try {
                  equalsConstructorPrototype(window[k]);
                } catch (e) {
                  return true;
                }
              }
            } catch (e) {
              return true;
            }
          }
          return false;
        })();
        equalsConstructorPrototypeIfNotBuggy = function(o) {
          if (typeof window === "undefined" || !hasAutomationEqualityBug) {
            return equalsConstructorPrototype(o);
          }
          try {
            return equalsConstructorPrototype(o);
          } catch (e) {
            return false;
          }
        };
        keysShim = function keys(object) {
          var isObject = object !== null && typeof object === "object";
          var isFunction = toStr.call(object) === "[object Function]";
          var isArguments = isArgs(object);
          var isString = isObject && toStr.call(object) === "[object String]";
          var theKeys = [];
          if (!isObject && !isFunction && !isArguments) {
            throw new TypeError("Object.keys called on a non-object");
          }
          var skipProto = hasProtoEnumBug && isFunction;
          if (isString && object.length > 0 && !has.call(object, 0)) {
            for (var i = 0; i < object.length; ++i) {
              theKeys.push(String(i));
            }
          }
          if (isArguments && object.length > 0) {
            for (var j = 0; j < object.length; ++j) {
              theKeys.push(String(j));
            }
          } else {
            for (var name in object) {
              if (!(skipProto && name === "prototype") && has.call(object, name)) {
                theKeys.push(String(name));
              }
            }
          }
          if (hasDontEnumBug) {
            var skipConstructor = equalsConstructorPrototypeIfNotBuggy(object);
            for (var k = 0; k < dontEnums.length; ++k) {
              if (!(skipConstructor && dontEnums[k] === "constructor") && has.call(object, dontEnums[k])) {
                theKeys.push(dontEnums[k]);
              }
            }
          }
          return theKeys;
        };
      }
      var has;
      var toStr;
      var isArgs;
      var isEnumerable;
      var hasDontEnumBug;
      var hasProtoEnumBug;
      var dontEnums;
      var equalsConstructorPrototype;
      var excludedKeys;
      var hasAutomationEqualityBug;
      var equalsConstructorPrototypeIfNotBuggy;
      module.exports = keysShim;
    }
  });

  // node_modules/object-keys/index.js
  var require_object_keys = __commonJS({
    "node_modules/object-keys/index.js"(exports, module) {
      "use strict";
      var slice = Array.prototype.slice;
      var isArgs = require_isArguments();
      var origKeys = Object.keys;
      var keysShim = origKeys ? function keys(o) {
        return origKeys(o);
      } : require_implementation2();
      var originalKeys = Object.keys;
      keysShim.shim = function shimObjectKeys() {
        if (Object.keys) {
          var keysWorksWithArguments = (function() {
            var args = Object.keys(arguments);
            return args && args.length === arguments.length;
          })(1, 2);
          if (!keysWorksWithArguments) {
            Object.keys = function keys(object) {
              if (isArgs(object)) {
                return originalKeys(slice.call(object));
              }
              return originalKeys(object);
            };
          }
        } else {
          Object.keys = keysShim;
        }
        return Object.keys || keysShim;
      };
      module.exports = keysShim;
    }
  });

  // node_modules/object.assign/implementation.js
  var require_implementation3 = __commonJS({
    "node_modules/object.assign/implementation.js"(exports, module) {
      "use strict";
      var objectKeys = require_object_keys();
      var hasSymbols = require_shams()();
      var callBound = require_call_bound();
      var $Object = require_es_object_atoms();
      var $push = callBound("Array.prototype.push");
      var $propIsEnumerable = callBound("Object.prototype.propertyIsEnumerable");
      var originalGetSymbols = hasSymbols ? $Object.getOwnPropertySymbols : null;
      module.exports = function assign(target, source1) {
        if (target == null) {
          throw new TypeError("target must be an object");
        }
        var to = $Object(target);
        if (arguments.length === 1) {
          return to;
        }
        for (var s = 1; s < arguments.length; ++s) {
          var from = $Object(arguments[s]);
          var keys = objectKeys(from);
          var getSymbols = hasSymbols && ($Object.getOwnPropertySymbols || originalGetSymbols);
          if (getSymbols) {
            var syms = getSymbols(from);
            for (var j = 0; j < syms.length; ++j) {
              var key = syms[j];
              if ($propIsEnumerable(from, key)) {
                $push(keys, key);
              }
            }
          }
          for (var i = 0; i < keys.length; ++i) {
            var nextKey = keys[i];
            if ($propIsEnumerable(from, nextKey)) {
              var propValue = from[nextKey];
              to[nextKey] = propValue;
            }
          }
        }
        return to;
      };
    }
  });

  // node_modules/object.assign/polyfill.js
  var require_polyfill = __commonJS({
    "node_modules/object.assign/polyfill.js"(exports, module) {
      "use strict";
      var implementation = require_implementation3();
      var lacksProperEnumerationOrder = function() {
        if (!Object.assign) {
          return false;
        }
        var str = "abcdefghijklmnopqrst";
        var letters = str.split("");
        var map = {};
        for (var i = 0; i < letters.length; ++i) {
          map[letters[i]] = letters[i];
        }
        var obj = Object.assign({}, map);
        var actual = "";
        for (var k in obj) {
          actual += k;
        }
        return str !== actual;
      };
      var assignHasPendingExceptions = function() {
        if (!Object.assign || !Object.preventExtensions) {
          return false;
        }
        var thrower = Object.preventExtensions({ 1: 2 });
        try {
          Object.assign(thrower, "xy");
        } catch (e) {
          return thrower[1] === "y";
        }
        return false;
      };
      module.exports = function getPolyfill() {
        if (!Object.assign) {
          return implementation;
        }
        if (lacksProperEnumerationOrder()) {
          return implementation;
        }
        if (assignHasPendingExceptions()) {
          return implementation;
        }
        return Object.assign;
      };
    }
  });

  // node_modules/object-is/implementation.js
  var require_implementation4 = __commonJS({
    "node_modules/object-is/implementation.js"(exports, module) {
      "use strict";
      var numberIsNaN = function(value) {
        return value !== value;
      };
      module.exports = function is(a, b) {
        if (a === 0 && b === 0) {
          return 1 / a === 1 / b;
        }
        if (a === b) {
          return true;
        }
        if (numberIsNaN(a) && numberIsNaN(b)) {
          return true;
        }
        return false;
      };
    }
  });

  // node_modules/object-is/polyfill.js
  var require_polyfill2 = __commonJS({
    "node_modules/object-is/polyfill.js"(exports, module) {
      "use strict";
      var implementation = require_implementation4();
      module.exports = function getPolyfill() {
        return typeof Object.is === "function" ? Object.is : implementation;
      };
    }
  });

  // node_modules/call-bind/callBound.js
  var require_callBound = __commonJS({
    "node_modules/call-bind/callBound.js"(exports, module) {
      "use strict";
      var GetIntrinsic = require_get_intrinsic();
      var callBind = require_call_bind();
      var $indexOf = callBind(GetIntrinsic("String.prototype.indexOf"));
      module.exports = function callBoundIntrinsic(name, allowMissing) {
        var intrinsic = GetIntrinsic(name, !!allowMissing);
        if (typeof intrinsic === "function" && $indexOf(name, ".prototype.") > -1) {
          return callBind(intrinsic);
        }
        return intrinsic;
      };
    }
  });

  // node_modules/define-properties/index.js
  var require_define_properties = __commonJS({
    "node_modules/define-properties/index.js"(exports, module) {
      "use strict";
      var keys = require_object_keys();
      var hasSymbols = typeof Symbol === "function" && typeof /* @__PURE__ */ Symbol("foo") === "symbol";
      var toStr = Object.prototype.toString;
      var concat = Array.prototype.concat;
      var defineDataProperty = require_define_data_property();
      var isFunction = function(fn) {
        return typeof fn === "function" && toStr.call(fn) === "[object Function]";
      };
      var supportsDescriptors = require_has_property_descriptors()();
      var defineProperty = function(object, name, value, predicate) {
        if (name in object) {
          if (predicate === true) {
            if (object[name] === value) {
              return;
            }
          } else if (!isFunction(predicate) || !predicate()) {
            return;
          }
        }
        if (supportsDescriptors) {
          defineDataProperty(object, name, value, true);
        } else {
          defineDataProperty(object, name, value);
        }
      };
      var defineProperties = function(object, map) {
        var predicates = arguments.length > 2 ? arguments[2] : {};
        var props = keys(map);
        if (hasSymbols) {
          props = concat.call(props, Object.getOwnPropertySymbols(map));
        }
        for (var i = 0; i < props.length; i += 1) {
          defineProperty(object, props[i], map[props[i]], predicates[props[i]]);
        }
      };
      defineProperties.supportsDescriptors = !!supportsDescriptors;
      module.exports = defineProperties;
    }
  });

  // node_modules/object-is/shim.js
  var require_shim = __commonJS({
    "node_modules/object-is/shim.js"(exports, module) {
      "use strict";
      var getPolyfill = require_polyfill2();
      var define2 = require_define_properties();
      module.exports = function shimObjectIs() {
        var polyfill = getPolyfill();
        define2(Object, { is: polyfill }, {
          is: function testObjectIs() {
            return Object.is !== polyfill;
          }
        });
        return polyfill;
      };
    }
  });

  // node_modules/object-is/index.js
  var require_object_is = __commonJS({
    "node_modules/object-is/index.js"(exports, module) {
      "use strict";
      var define2 = require_define_properties();
      var callBind = require_call_bind();
      var implementation = require_implementation4();
      var getPolyfill = require_polyfill2();
      var shim = require_shim();
      var polyfill = callBind(getPolyfill(), Object);
      define2(polyfill, {
        getPolyfill,
        implementation,
        shim
      });
      module.exports = polyfill;
    }
  });

  // node_modules/is-nan/implementation.js
  var require_implementation5 = __commonJS({
    "node_modules/is-nan/implementation.js"(exports, module) {
      "use strict";
      module.exports = function isNaN2(value) {
        return value !== value;
      };
    }
  });

  // node_modules/is-nan/polyfill.js
  var require_polyfill3 = __commonJS({
    "node_modules/is-nan/polyfill.js"(exports, module) {
      "use strict";
      var implementation = require_implementation5();
      module.exports = function getPolyfill() {
        if (Number.isNaN && Number.isNaN(NaN) && !Number.isNaN("a")) {
          return Number.isNaN;
        }
        return implementation;
      };
    }
  });

  // node_modules/is-nan/shim.js
  var require_shim2 = __commonJS({
    "node_modules/is-nan/shim.js"(exports, module) {
      "use strict";
      var define2 = require_define_properties();
      var getPolyfill = require_polyfill3();
      module.exports = function shimNumberIsNaN() {
        var polyfill = getPolyfill();
        define2(Number, { isNaN: polyfill }, {
          isNaN: function testIsNaN() {
            return Number.isNaN !== polyfill;
          }
        });
        return polyfill;
      };
    }
  });

  // node_modules/is-nan/index.js
  var require_is_nan = __commonJS({
    "node_modules/is-nan/index.js"(exports, module) {
      "use strict";
      var callBind = require_call_bind();
      var define2 = require_define_properties();
      var implementation = require_implementation5();
      var getPolyfill = require_polyfill3();
      var shim = require_shim2();
      var polyfill = callBind(getPolyfill(), Number);
      define2(polyfill, {
        getPolyfill,
        implementation,
        shim
      });
      module.exports = polyfill;
    }
  });

  // node_modules/assert/build/internal/util/comparisons.js
  var require_comparisons = __commonJS({
    "node_modules/assert/build/internal/util/comparisons.js"(exports, module) {
      "use strict";
      function _slicedToArray(arr, i) {
        return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest();
      }
      function _nonIterableRest() {
        throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
      }
      function _unsupportedIterableToArray(o, minLen) {
        if (!o) return;
        if (typeof o === "string") return _arrayLikeToArray(o, minLen);
        var n = Object.prototype.toString.call(o).slice(8, -1);
        if (n === "Object" && o.constructor) n = o.constructor.name;
        if (n === "Map" || n === "Set") return Array.from(o);
        if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
      }
      function _arrayLikeToArray(arr, len) {
        if (len == null || len > arr.length) len = arr.length;
        for (var i = 0, arr2 = new Array(len); i < len; i++) arr2[i] = arr[i];
        return arr2;
      }
      function _iterableToArrayLimit(r, l) {
        var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"];
        if (null != t) {
          var e, n, i, u, a = [], f = true, o = false;
          try {
            if (i = (t = t.call(r)).next, 0 === l) {
              if (Object(t) !== t) return;
              f = false;
            } else for (; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = true) ;
          } catch (r2) {
            o = true, n = r2;
          } finally {
            try {
              if (!f && null != t.return && (u = t.return(), Object(u) !== u)) return;
            } finally {
              if (o) throw n;
            }
          }
          return a;
        }
      }
      function _arrayWithHoles(arr) {
        if (Array.isArray(arr)) return arr;
      }
      function _typeof(o) {
        "@babel/helpers - typeof";
        return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o2) {
          return typeof o2;
        } : function(o2) {
          return o2 && "function" == typeof Symbol && o2.constructor === Symbol && o2 !== Symbol.prototype ? "symbol" : typeof o2;
        }, _typeof(o);
      }
      var regexFlagsSupported = /a/g.flags !== void 0;
      var arrayFromSet = function arrayFromSet2(set) {
        var array = [];
        set.forEach(function(value) {
          return array.push(value);
        });
        return array;
      };
      var arrayFromMap = function arrayFromMap2(map) {
        var array = [];
        map.forEach(function(value, key) {
          return array.push([key, value]);
        });
        return array;
      };
      var objectIs = Object.is ? Object.is : require_object_is();
      var objectGetOwnPropertySymbols = Object.getOwnPropertySymbols ? Object.getOwnPropertySymbols : function() {
        return [];
      };
      var numberIsNaN = Number.isNaN ? Number.isNaN : require_is_nan();
      function uncurryThis(f) {
        return f.call.bind(f);
      }
      var hasOwnProperty = uncurryThis(Object.prototype.hasOwnProperty);
      var propertyIsEnumerable = uncurryThis(Object.prototype.propertyIsEnumerable);
      var objectToString = uncurryThis(Object.prototype.toString);
      var _require$types = require_util().types;
      var isAnyArrayBuffer = _require$types.isAnyArrayBuffer;
      var isArrayBufferView = _require$types.isArrayBufferView;
      var isDate = _require$types.isDate;
      var isMap = _require$types.isMap;
      var isRegExp = _require$types.isRegExp;
      var isSet = _require$types.isSet;
      var isNativeError = _require$types.isNativeError;
      var isBoxedPrimitive = _require$types.isBoxedPrimitive;
      var isNumberObject = _require$types.isNumberObject;
      var isStringObject = _require$types.isStringObject;
      var isBooleanObject = _require$types.isBooleanObject;
      var isBigIntObject = _require$types.isBigIntObject;
      var isSymbolObject = _require$types.isSymbolObject;
      var isFloat32Array = _require$types.isFloat32Array;
      var isFloat64Array = _require$types.isFloat64Array;
      function isNonIndex(key) {
        if (key.length === 0 || key.length > 10) return true;
        for (var i = 0; i < key.length; i++) {
          var code = key.charCodeAt(i);
          if (code < 48 || code > 57) return true;
        }
        return key.length === 10 && key >= Math.pow(2, 32);
      }
      function getOwnNonIndexProperties(value) {
        return Object.keys(value).filter(isNonIndex).concat(objectGetOwnPropertySymbols(value).filter(Object.prototype.propertyIsEnumerable.bind(value)));
      }
      function compare(a, b) {
        if (a === b) {
          return 0;
        }
        var x = a.length;
        var y = b.length;
        for (var i = 0, len = Math.min(x, y); i < len; ++i) {
          if (a[i] !== b[i]) {
            x = a[i];
            y = b[i];
            break;
          }
        }
        if (x < y) {
          return -1;
        }
        if (y < x) {
          return 1;
        }
        return 0;
      }
      var ONLY_ENUMERABLE = void 0;
      var kStrict = true;
      var kLoose = false;
      var kNoIterator = 0;
      var kIsArray = 1;
      var kIsSet = 2;
      var kIsMap = 3;
      function areSimilarRegExps(a, b) {
        return regexFlagsSupported ? a.source === b.source && a.flags === b.flags : RegExp.prototype.toString.call(a) === RegExp.prototype.toString.call(b);
      }
      function areSimilarFloatArrays(a, b) {
        if (a.byteLength !== b.byteLength) {
          return false;
        }
        for (var offset = 0; offset < a.byteLength; offset++) {
          if (a[offset] !== b[offset]) {
            return false;
          }
        }
        return true;
      }
      function areSimilarTypedArrays(a, b) {
        if (a.byteLength !== b.byteLength) {
          return false;
        }
        return compare(new Uint8Array(a.buffer, a.byteOffset, a.byteLength), new Uint8Array(b.buffer, b.byteOffset, b.byteLength)) === 0;
      }
      function areEqualArrayBuffers(buf1, buf2) {
        return buf1.byteLength === buf2.byteLength && compare(new Uint8Array(buf1), new Uint8Array(buf2)) === 0;
      }
      function isEqualBoxedPrimitive(val1, val2) {
        if (isNumberObject(val1)) {
          return isNumberObject(val2) && objectIs(Number.prototype.valueOf.call(val1), Number.prototype.valueOf.call(val2));
        }
        if (isStringObject(val1)) {
          return isStringObject(val2) && String.prototype.valueOf.call(val1) === String.prototype.valueOf.call(val2);
        }
        if (isBooleanObject(val1)) {
          return isBooleanObject(val2) && Boolean.prototype.valueOf.call(val1) === Boolean.prototype.valueOf.call(val2);
        }
        if (isBigIntObject(val1)) {
          return isBigIntObject(val2) && BigInt.prototype.valueOf.call(val1) === BigInt.prototype.valueOf.call(val2);
        }
        return isSymbolObject(val2) && Symbol.prototype.valueOf.call(val1) === Symbol.prototype.valueOf.call(val2);
      }
      function innerDeepEqual(val1, val2, strict, memos) {
        if (val1 === val2) {
          if (val1 !== 0) return true;
          return strict ? objectIs(val1, val2) : true;
        }
        if (strict) {
          if (_typeof(val1) !== "object") {
            return typeof val1 === "number" && numberIsNaN(val1) && numberIsNaN(val2);
          }
          if (_typeof(val2) !== "object" || val1 === null || val2 === null) {
            return false;
          }
          if (Object.getPrototypeOf(val1) !== Object.getPrototypeOf(val2)) {
            return false;
          }
        } else {
          if (val1 === null || _typeof(val1) !== "object") {
            if (val2 === null || _typeof(val2) !== "object") {
              return val1 == val2;
            }
            return false;
          }
          if (val2 === null || _typeof(val2) !== "object") {
            return false;
          }
        }
        var val1Tag = objectToString(val1);
        var val2Tag = objectToString(val2);
        if (val1Tag !== val2Tag) {
          return false;
        }
        if (Array.isArray(val1)) {
          if (val1.length !== val2.length) {
            return false;
          }
          var keys1 = getOwnNonIndexProperties(val1, ONLY_ENUMERABLE);
          var keys2 = getOwnNonIndexProperties(val2, ONLY_ENUMERABLE);
          if (keys1.length !== keys2.length) {
            return false;
          }
          return keyCheck(val1, val2, strict, memos, kIsArray, keys1);
        }
        if (val1Tag === "[object Object]") {
          if (!isMap(val1) && isMap(val2) || !isSet(val1) && isSet(val2)) {
            return false;
          }
        }
        if (isDate(val1)) {
          if (!isDate(val2) || Date.prototype.getTime.call(val1) !== Date.prototype.getTime.call(val2)) {
            return false;
          }
        } else if (isRegExp(val1)) {
          if (!isRegExp(val2) || !areSimilarRegExps(val1, val2)) {
            return false;
          }
        } else if (isNativeError(val1) || val1 instanceof Error) {
          if (val1.message !== val2.message || val1.name !== val2.name) {
            return false;
          }
        } else if (isArrayBufferView(val1)) {
          if (!strict && (isFloat32Array(val1) || isFloat64Array(val1))) {
            if (!areSimilarFloatArrays(val1, val2)) {
              return false;
            }
          } else if (!areSimilarTypedArrays(val1, val2)) {
            return false;
          }
          var _keys = getOwnNonIndexProperties(val1, ONLY_ENUMERABLE);
          var _keys2 = getOwnNonIndexProperties(val2, ONLY_ENUMERABLE);
          if (_keys.length !== _keys2.length) {
            return false;
          }
          return keyCheck(val1, val2, strict, memos, kNoIterator, _keys);
        } else if (isSet(val1)) {
          if (!isSet(val2) || val1.size !== val2.size) {
            return false;
          }
          return keyCheck(val1, val2, strict, memos, kIsSet);
        } else if (isMap(val1)) {
          if (!isMap(val2) || val1.size !== val2.size) {
            return false;
          }
          return keyCheck(val1, val2, strict, memos, kIsMap);
        } else if (isAnyArrayBuffer(val1)) {
          if (!areEqualArrayBuffers(val1, val2)) {
            return false;
          }
        } else if (isBoxedPrimitive(val1) && !isEqualBoxedPrimitive(val1, val2)) {
          return false;
        }
        return keyCheck(val1, val2, strict, memos, kNoIterator);
      }
      function getEnumerables(val, keys) {
        return keys.filter(function(k) {
          return propertyIsEnumerable(val, k);
        });
      }
      function keyCheck(val1, val2, strict, memos, iterationType, aKeys) {
        if (arguments.length === 5) {
          aKeys = Object.keys(val1);
          var bKeys = Object.keys(val2);
          if (aKeys.length !== bKeys.length) {
            return false;
          }
        }
        var i = 0;
        for (; i < aKeys.length; i++) {
          if (!hasOwnProperty(val2, aKeys[i])) {
            return false;
          }
        }
        if (strict && arguments.length === 5) {
          var symbolKeysA = objectGetOwnPropertySymbols(val1);
          if (symbolKeysA.length !== 0) {
            var count = 0;
            for (i = 0; i < symbolKeysA.length; i++) {
              var key = symbolKeysA[i];
              if (propertyIsEnumerable(val1, key)) {
                if (!propertyIsEnumerable(val2, key)) {
                  return false;
                }
                aKeys.push(key);
                count++;
              } else if (propertyIsEnumerable(val2, key)) {
                return false;
              }
            }
            var symbolKeysB = objectGetOwnPropertySymbols(val2);
            if (symbolKeysA.length !== symbolKeysB.length && getEnumerables(val2, symbolKeysB).length !== count) {
              return false;
            }
          } else {
            var _symbolKeysB = objectGetOwnPropertySymbols(val2);
            if (_symbolKeysB.length !== 0 && getEnumerables(val2, _symbolKeysB).length !== 0) {
              return false;
            }
          }
        }
        if (aKeys.length === 0 && (iterationType === kNoIterator || iterationType === kIsArray && val1.length === 0 || val1.size === 0)) {
          return true;
        }
        if (memos === void 0) {
          memos = {
            val1: /* @__PURE__ */ new Map(),
            val2: /* @__PURE__ */ new Map(),
            position: 0
          };
        } else {
          var val2MemoA = memos.val1.get(val1);
          if (val2MemoA !== void 0) {
            var val2MemoB = memos.val2.get(val2);
            if (val2MemoB !== void 0) {
              return val2MemoA === val2MemoB;
            }
          }
          memos.position++;
        }
        memos.val1.set(val1, memos.position);
        memos.val2.set(val2, memos.position);
        var areEq = objEquiv(val1, val2, strict, aKeys, memos, iterationType);
        memos.val1.delete(val1);
        memos.val2.delete(val2);
        return areEq;
      }
      function setHasEqualElement(set, val1, strict, memo) {
        var setValues = arrayFromSet(set);
        for (var i = 0; i < setValues.length; i++) {
          var val2 = setValues[i];
          if (innerDeepEqual(val1, val2, strict, memo)) {
            set.delete(val2);
            return true;
          }
        }
        return false;
      }
      function findLooseMatchingPrimitives(prim) {
        switch (_typeof(prim)) {
          case "undefined":
            return null;
          case "object":
            return void 0;
          case "symbol":
            return false;
          case "string":
            prim = +prim;
          // Loose equal entries exist only if the string is possible to convert to
          // a regular number and not NaN.
          // Fall through
          case "number":
            if (numberIsNaN(prim)) {
              return false;
            }
        }
        return true;
      }
      function setMightHaveLoosePrim(a, b, prim) {
        var altValue = findLooseMatchingPrimitives(prim);
        if (altValue != null) return altValue;
        return b.has(altValue) && !a.has(altValue);
      }
      function mapMightHaveLoosePrim(a, b, prim, item, memo) {
        var altValue = findLooseMatchingPrimitives(prim);
        if (altValue != null) {
          return altValue;
        }
        var curB = b.get(altValue);
        if (curB === void 0 && !b.has(altValue) || !innerDeepEqual(item, curB, false, memo)) {
          return false;
        }
        return !a.has(altValue) && innerDeepEqual(item, curB, false, memo);
      }
      function setEquiv(a, b, strict, memo) {
        var set = null;
        var aValues = arrayFromSet(a);
        for (var i = 0; i < aValues.length; i++) {
          var val = aValues[i];
          if (_typeof(val) === "object" && val !== null) {
            if (set === null) {
              set = /* @__PURE__ */ new Set();
            }
            set.add(val);
          } else if (!b.has(val)) {
            if (strict) return false;
            if (!setMightHaveLoosePrim(a, b, val)) {
              return false;
            }
            if (set === null) {
              set = /* @__PURE__ */ new Set();
            }
            set.add(val);
          }
        }
        if (set !== null) {
          var bValues = arrayFromSet(b);
          for (var _i = 0; _i < bValues.length; _i++) {
            var _val = bValues[_i];
            if (_typeof(_val) === "object" && _val !== null) {
              if (!setHasEqualElement(set, _val, strict, memo)) return false;
            } else if (!strict && !a.has(_val) && !setHasEqualElement(set, _val, strict, memo)) {
              return false;
            }
          }
          return set.size === 0;
        }
        return true;
      }
      function mapHasEqualEntry(set, map, key1, item1, strict, memo) {
        var setValues = arrayFromSet(set);
        for (var i = 0; i < setValues.length; i++) {
          var key2 = setValues[i];
          if (innerDeepEqual(key1, key2, strict, memo) && innerDeepEqual(item1, map.get(key2), strict, memo)) {
            set.delete(key2);
            return true;
          }
        }
        return false;
      }
      function mapEquiv(a, b, strict, memo) {
        var set = null;
        var aEntries = arrayFromMap(a);
        for (var i = 0; i < aEntries.length; i++) {
          var _aEntries$i = _slicedToArray(aEntries[i], 2), key = _aEntries$i[0], item1 = _aEntries$i[1];
          if (_typeof(key) === "object" && key !== null) {
            if (set === null) {
              set = /* @__PURE__ */ new Set();
            }
            set.add(key);
          } else {
            var item2 = b.get(key);
            if (item2 === void 0 && !b.has(key) || !innerDeepEqual(item1, item2, strict, memo)) {
              if (strict) return false;
              if (!mapMightHaveLoosePrim(a, b, key, item1, memo)) return false;
              if (set === null) {
                set = /* @__PURE__ */ new Set();
              }
              set.add(key);
            }
          }
        }
        if (set !== null) {
          var bEntries = arrayFromMap(b);
          for (var _i2 = 0; _i2 < bEntries.length; _i2++) {
            var _bEntries$_i = _slicedToArray(bEntries[_i2], 2), _key = _bEntries$_i[0], item = _bEntries$_i[1];
            if (_typeof(_key) === "object" && _key !== null) {
              if (!mapHasEqualEntry(set, a, _key, item, strict, memo)) return false;
            } else if (!strict && (!a.has(_key) || !innerDeepEqual(a.get(_key), item, false, memo)) && !mapHasEqualEntry(set, a, _key, item, false, memo)) {
              return false;
            }
          }
          return set.size === 0;
        }
        return true;
      }
      function objEquiv(a, b, strict, keys, memos, iterationType) {
        var i = 0;
        if (iterationType === kIsSet) {
          if (!setEquiv(a, b, strict, memos)) {
            return false;
          }
        } else if (iterationType === kIsMap) {
          if (!mapEquiv(a, b, strict, memos)) {
            return false;
          }
        } else if (iterationType === kIsArray) {
          for (; i < a.length; i++) {
            if (hasOwnProperty(a, i)) {
              if (!hasOwnProperty(b, i) || !innerDeepEqual(a[i], b[i], strict, memos)) {
                return false;
              }
            } else if (hasOwnProperty(b, i)) {
              return false;
            } else {
              var keysA = Object.keys(a);
              for (; i < keysA.length; i++) {
                var key = keysA[i];
                if (!hasOwnProperty(b, key) || !innerDeepEqual(a[key], b[key], strict, memos)) {
                  return false;
                }
              }
              if (keysA.length !== Object.keys(b).length) {
                return false;
              }
              return true;
            }
          }
        }
        for (i = 0; i < keys.length; i++) {
          var _key2 = keys[i];
          if (!innerDeepEqual(a[_key2], b[_key2], strict, memos)) {
            return false;
          }
        }
        return true;
      }
      function isDeepEqual(val1, val2) {
        return innerDeepEqual(val1, val2, kLoose);
      }
      function isDeepStrictEqual(val1, val2) {
        return innerDeepEqual(val1, val2, kStrict);
      }
      module.exports = {
        isDeepEqual,
        isDeepStrictEqual
      };
    }
  });

  // node_modules/assert/build/assert.js
  var require_assert = __commonJS({
    "node_modules/assert/build/assert.js"(exports, module) {
      "use strict";
      function _typeof(o) {
        "@babel/helpers - typeof";
        return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o2) {
          return typeof o2;
        } : function(o2) {
          return o2 && "function" == typeof Symbol && o2.constructor === Symbol && o2 !== Symbol.prototype ? "symbol" : typeof o2;
        }, _typeof(o);
      }
      function _defineProperties(target, props) {
        for (var i = 0; i < props.length; i++) {
          var descriptor = props[i];
          descriptor.enumerable = descriptor.enumerable || false;
          descriptor.configurable = true;
          if ("value" in descriptor) descriptor.writable = true;
          Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
        }
      }
      function _createClass(Constructor, protoProps, staticProps) {
        if (protoProps) _defineProperties(Constructor.prototype, protoProps);
        if (staticProps) _defineProperties(Constructor, staticProps);
        Object.defineProperty(Constructor, "prototype", { writable: false });
        return Constructor;
      }
      function _toPropertyKey(arg) {
        var key = _toPrimitive(arg, "string");
        return _typeof(key) === "symbol" ? key : String(key);
      }
      function _toPrimitive(input, hint) {
        if (_typeof(input) !== "object" || input === null) return input;
        var prim = input[Symbol.toPrimitive];
        if (prim !== void 0) {
          var res = prim.call(input, hint || "default");
          if (_typeof(res) !== "object") return res;
          throw new TypeError("@@toPrimitive must return a primitive value.");
        }
        return (hint === "string" ? String : Number)(input);
      }
      function _classCallCheck(instance, Constructor) {
        if (!(instance instanceof Constructor)) {
          throw new TypeError("Cannot call a class as a function");
        }
      }
      var _require = require_errors();
      var _require$codes = _require.codes;
      var ERR_AMBIGUOUS_ARGUMENT = _require$codes.ERR_AMBIGUOUS_ARGUMENT;
      var ERR_INVALID_ARG_TYPE = _require$codes.ERR_INVALID_ARG_TYPE;
      var ERR_INVALID_ARG_VALUE = _require$codes.ERR_INVALID_ARG_VALUE;
      var ERR_INVALID_RETURN_VALUE = _require$codes.ERR_INVALID_RETURN_VALUE;
      var ERR_MISSING_ARGS = _require$codes.ERR_MISSING_ARGS;
      var AssertionError = require_assertion_error();
      var _require2 = require_util();
      var inspect = _require2.inspect;
      var _require$types = require_util().types;
      var isPromise = _require$types.isPromise;
      var isRegExp = _require$types.isRegExp;
      var objectAssign = require_polyfill()();
      var objectIs = require_polyfill2()();
      var RegExpPrototypeTest = require_callBound()("RegExp.prototype.test");
      var isDeepEqual;
      var isDeepStrictEqual;
      function lazyLoadComparison() {
        var comparison = require_comparisons();
        isDeepEqual = comparison.isDeepEqual;
        isDeepStrictEqual = comparison.isDeepStrictEqual;
      }
      var warned = false;
      var assert = module.exports = ok;
      var NO_EXCEPTION_SENTINEL = {};
      function innerFail(obj) {
        if (obj.message instanceof Error) throw obj.message;
        throw new AssertionError(obj);
      }
      function fail(actual, expected, message, operator, stackStartFn) {
        var argsLen = arguments.length;
        var internalMessage;
        if (argsLen === 0) {
          internalMessage = "Failed";
        } else if (argsLen === 1) {
          message = actual;
          actual = void 0;
        } else {
          if (warned === false) {
            warned = true;
            var warn = process.emitWarning ? process.emitWarning : console.warn.bind(console);
            warn("assert.fail() with more than one argument is deprecated. Please use assert.strictEqual() instead or only pass a message.", "DeprecationWarning", "DEP0094");
          }
          if (argsLen === 2) operator = "!=";
        }
        if (message instanceof Error) throw message;
        var errArgs = {
          actual,
          expected,
          operator: operator === void 0 ? "fail" : operator,
          stackStartFn: stackStartFn || fail
        };
        if (message !== void 0) {
          errArgs.message = message;
        }
        var err = new AssertionError(errArgs);
        if (internalMessage) {
          err.message = internalMessage;
          err.generatedMessage = true;
        }
        throw err;
      }
      assert.fail = fail;
      assert.AssertionError = AssertionError;
      function innerOk(fn, argLen, value, message) {
        if (!value) {
          var generatedMessage = false;
          if (argLen === 0) {
            generatedMessage = true;
            message = "No value argument passed to `assert.ok()`";
          } else if (message instanceof Error) {
            throw message;
          }
          var err = new AssertionError({
            actual: value,
            expected: true,
            message,
            operator: "==",
            stackStartFn: fn
          });
          err.generatedMessage = generatedMessage;
          throw err;
        }
      }
      function ok() {
        for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
          args[_key] = arguments[_key];
        }
        innerOk.apply(void 0, [ok, args.length].concat(args));
      }
      assert.ok = ok;
      assert.equal = function equal(actual, expected, message) {
        if (arguments.length < 2) {
          throw new ERR_MISSING_ARGS("actual", "expected");
        }
        if (actual != expected) {
          innerFail({
            actual,
            expected,
            message,
            operator: "==",
            stackStartFn: equal
          });
        }
      };
      assert.notEqual = function notEqual(actual, expected, message) {
        if (arguments.length < 2) {
          throw new ERR_MISSING_ARGS("actual", "expected");
        }
        if (actual == expected) {
          innerFail({
            actual,
            expected,
            message,
            operator: "!=",
            stackStartFn: notEqual
          });
        }
      };
      assert.deepEqual = function deepEqual(actual, expected, message) {
        if (arguments.length < 2) {
          throw new ERR_MISSING_ARGS("actual", "expected");
        }
        if (isDeepEqual === void 0) lazyLoadComparison();
        if (!isDeepEqual(actual, expected)) {
          innerFail({
            actual,
            expected,
            message,
            operator: "deepEqual",
            stackStartFn: deepEqual
          });
        }
      };
      assert.notDeepEqual = function notDeepEqual(actual, expected, message) {
        if (arguments.length < 2) {
          throw new ERR_MISSING_ARGS("actual", "expected");
        }
        if (isDeepEqual === void 0) lazyLoadComparison();
        if (isDeepEqual(actual, expected)) {
          innerFail({
            actual,
            expected,
            message,
            operator: "notDeepEqual",
            stackStartFn: notDeepEqual
          });
        }
      };
      assert.deepStrictEqual = function deepStrictEqual(actual, expected, message) {
        if (arguments.length < 2) {
          throw new ERR_MISSING_ARGS("actual", "expected");
        }
        if (isDeepEqual === void 0) lazyLoadComparison();
        if (!isDeepStrictEqual(actual, expected)) {
          innerFail({
            actual,
            expected,
            message,
            operator: "deepStrictEqual",
            stackStartFn: deepStrictEqual
          });
        }
      };
      assert.notDeepStrictEqual = notDeepStrictEqual;
      function notDeepStrictEqual(actual, expected, message) {
        if (arguments.length < 2) {
          throw new ERR_MISSING_ARGS("actual", "expected");
        }
        if (isDeepEqual === void 0) lazyLoadComparison();
        if (isDeepStrictEqual(actual, expected)) {
          innerFail({
            actual,
            expected,
            message,
            operator: "notDeepStrictEqual",
            stackStartFn: notDeepStrictEqual
          });
        }
      }
      assert.strictEqual = function strictEqual(actual, expected, message) {
        if (arguments.length < 2) {
          throw new ERR_MISSING_ARGS("actual", "expected");
        }
        if (!objectIs(actual, expected)) {
          innerFail({
            actual,
            expected,
            message,
            operator: "strictEqual",
            stackStartFn: strictEqual
          });
        }
      };
      assert.notStrictEqual = function notStrictEqual(actual, expected, message) {
        if (arguments.length < 2) {
          throw new ERR_MISSING_ARGS("actual", "expected");
        }
        if (objectIs(actual, expected)) {
          innerFail({
            actual,
            expected,
            message,
            operator: "notStrictEqual",
            stackStartFn: notStrictEqual
          });
        }
      };
      var Comparison = /* @__PURE__ */ _createClass(function Comparison2(obj, keys, actual) {
        var _this = this;
        _classCallCheck(this, Comparison2);
        keys.forEach(function(key) {
          if (key in obj) {
            if (actual !== void 0 && typeof actual[key] === "string" && isRegExp(obj[key]) && RegExpPrototypeTest(obj[key], actual[key])) {
              _this[key] = actual[key];
            } else {
              _this[key] = obj[key];
            }
          }
        });
      });
      function compareExceptionKey(actual, expected, key, message, keys, fn) {
        if (!(key in actual) || !isDeepStrictEqual(actual[key], expected[key])) {
          if (!message) {
            var a = new Comparison(actual, keys);
            var b = new Comparison(expected, keys, actual);
            var err = new AssertionError({
              actual: a,
              expected: b,
              operator: "deepStrictEqual",
              stackStartFn: fn
            });
            err.actual = actual;
            err.expected = expected;
            err.operator = fn.name;
            throw err;
          }
          innerFail({
            actual,
            expected,
            message,
            operator: fn.name,
            stackStartFn: fn
          });
        }
      }
      function expectedException(actual, expected, msg, fn) {
        if (typeof expected !== "function") {
          if (isRegExp(expected)) return RegExpPrototypeTest(expected, actual);
          if (arguments.length === 2) {
            throw new ERR_INVALID_ARG_TYPE("expected", ["Function", "RegExp"], expected);
          }
          if (_typeof(actual) !== "object" || actual === null) {
            var err = new AssertionError({
              actual,
              expected,
              message: msg,
              operator: "deepStrictEqual",
              stackStartFn: fn
            });
            err.operator = fn.name;
            throw err;
          }
          var keys = Object.keys(expected);
          if (expected instanceof Error) {
            keys.push("name", "message");
          } else if (keys.length === 0) {
            throw new ERR_INVALID_ARG_VALUE("error", expected, "may not be an empty object");
          }
          if (isDeepEqual === void 0) lazyLoadComparison();
          keys.forEach(function(key) {
            if (typeof actual[key] === "string" && isRegExp(expected[key]) && RegExpPrototypeTest(expected[key], actual[key])) {
              return;
            }
            compareExceptionKey(actual, expected, key, msg, keys, fn);
          });
          return true;
        }
        if (expected.prototype !== void 0 && actual instanceof expected) {
          return true;
        }
        if (Error.isPrototypeOf(expected)) {
          return false;
        }
        return expected.call({}, actual) === true;
      }
      function getActual(fn) {
        if (typeof fn !== "function") {
          throw new ERR_INVALID_ARG_TYPE("fn", "Function", fn);
        }
        try {
          fn();
        } catch (e) {
          return e;
        }
        return NO_EXCEPTION_SENTINEL;
      }
      function checkIsPromise(obj) {
        return isPromise(obj) || obj !== null && _typeof(obj) === "object" && typeof obj.then === "function" && typeof obj.catch === "function";
      }
      function waitForActual(promiseFn) {
        return Promise.resolve().then(function() {
          var resultPromise;
          if (typeof promiseFn === "function") {
            resultPromise = promiseFn();
            if (!checkIsPromise(resultPromise)) {
              throw new ERR_INVALID_RETURN_VALUE("instance of Promise", "promiseFn", resultPromise);
            }
          } else if (checkIsPromise(promiseFn)) {
            resultPromise = promiseFn;
          } else {
            throw new ERR_INVALID_ARG_TYPE("promiseFn", ["Function", "Promise"], promiseFn);
          }
          return Promise.resolve().then(function() {
            return resultPromise;
          }).then(function() {
            return NO_EXCEPTION_SENTINEL;
          }).catch(function(e) {
            return e;
          });
        });
      }
      function expectsError(stackStartFn, actual, error, message) {
        if (typeof error === "string") {
          if (arguments.length === 4) {
            throw new ERR_INVALID_ARG_TYPE("error", ["Object", "Error", "Function", "RegExp"], error);
          }
          if (_typeof(actual) === "object" && actual !== null) {
            if (actual.message === error) {
              throw new ERR_AMBIGUOUS_ARGUMENT("error/message", 'The error message "'.concat(actual.message, '" is identical to the message.'));
            }
          } else if (actual === error) {
            throw new ERR_AMBIGUOUS_ARGUMENT("error/message", 'The error "'.concat(actual, '" is identical to the message.'));
          }
          message = error;
          error = void 0;
        } else if (error != null && _typeof(error) !== "object" && typeof error !== "function") {
          throw new ERR_INVALID_ARG_TYPE("error", ["Object", "Error", "Function", "RegExp"], error);
        }
        if (actual === NO_EXCEPTION_SENTINEL) {
          var details = "";
          if (error && error.name) {
            details += " (".concat(error.name, ")");
          }
          details += message ? ": ".concat(message) : ".";
          var fnType = stackStartFn.name === "rejects" ? "rejection" : "exception";
          innerFail({
            actual: void 0,
            expected: error,
            operator: stackStartFn.name,
            message: "Missing expected ".concat(fnType).concat(details),
            stackStartFn
          });
        }
        if (error && !expectedException(actual, error, message, stackStartFn)) {
          throw actual;
        }
      }
      function expectsNoError(stackStartFn, actual, error, message) {
        if (actual === NO_EXCEPTION_SENTINEL) return;
        if (typeof error === "string") {
          message = error;
          error = void 0;
        }
        if (!error || expectedException(actual, error)) {
          var details = message ? ": ".concat(message) : ".";
          var fnType = stackStartFn.name === "doesNotReject" ? "rejection" : "exception";
          innerFail({
            actual,
            expected: error,
            operator: stackStartFn.name,
            message: "Got unwanted ".concat(fnType).concat(details, "\n") + 'Actual message: "'.concat(actual && actual.message, '"'),
            stackStartFn
          });
        }
        throw actual;
      }
      assert.throws = function throws(promiseFn) {
        for (var _len2 = arguments.length, args = new Array(_len2 > 1 ? _len2 - 1 : 0), _key2 = 1; _key2 < _len2; _key2++) {
          args[_key2 - 1] = arguments[_key2];
        }
        expectsError.apply(void 0, [throws, getActual(promiseFn)].concat(args));
      };
      assert.rejects = function rejects(promiseFn) {
        for (var _len3 = arguments.length, args = new Array(_len3 > 1 ? _len3 - 1 : 0), _key3 = 1; _key3 < _len3; _key3++) {
          args[_key3 - 1] = arguments[_key3];
        }
        return waitForActual(promiseFn).then(function(result) {
          return expectsError.apply(void 0, [rejects, result].concat(args));
        });
      };
      assert.doesNotThrow = function doesNotThrow(fn) {
        for (var _len4 = arguments.length, args = new Array(_len4 > 1 ? _len4 - 1 : 0), _key4 = 1; _key4 < _len4; _key4++) {
          args[_key4 - 1] = arguments[_key4];
        }
        expectsNoError.apply(void 0, [doesNotThrow, getActual(fn)].concat(args));
      };
      assert.doesNotReject = function doesNotReject(fn) {
        for (var _len5 = arguments.length, args = new Array(_len5 > 1 ? _len5 - 1 : 0), _key5 = 1; _key5 < _len5; _key5++) {
          args[_key5 - 1] = arguments[_key5];
        }
        return waitForActual(fn).then(function(result) {
          return expectsNoError.apply(void 0, [doesNotReject, result].concat(args));
        });
      };
      assert.ifError = function ifError(err) {
        if (err !== null && err !== void 0) {
          var message = "ifError got unwanted exception: ";
          if (_typeof(err) === "object" && typeof err.message === "string") {
            if (err.message.length === 0 && err.constructor) {
              message += err.constructor.name;
            } else {
              message += err.message;
            }
          } else {
            message += inspect(err);
          }
          var newErr = new AssertionError({
            actual: err,
            expected: null,
            operator: "ifError",
            message,
            stackStartFn: ifError
          });
          var origStack = err.stack;
          if (typeof origStack === "string") {
            var tmp2 = origStack.split("\n");
            tmp2.shift();
            var tmp1 = newErr.stack.split("\n");
            for (var i = 0; i < tmp2.length; i++) {
              var pos = tmp1.indexOf(tmp2[i]);
              if (pos !== -1) {
                tmp1 = tmp1.slice(0, pos);
                break;
              }
            }
            newErr.stack = "".concat(tmp1.join("\n"), "\n").concat(tmp2.join("\n"));
          }
          throw newErr;
        }
      };
      function internalMatch(string, regexp, message, fn, fnName) {
        if (!isRegExp(regexp)) {
          throw new ERR_INVALID_ARG_TYPE("regexp", "RegExp", regexp);
        }
        var match = fnName === "match";
        if (typeof string !== "string" || RegExpPrototypeTest(regexp, string) !== match) {
          if (message instanceof Error) {
            throw message;
          }
          var generatedMessage = !message;
          message = message || (typeof string !== "string" ? 'The "string" argument must be of type string. Received type ' + "".concat(_typeof(string), " (").concat(inspect(string), ")") : (match ? "The input did not match the regular expression " : "The input was expected to not match the regular expression ") + "".concat(inspect(regexp), ". Input:\n\n").concat(inspect(string), "\n"));
          var err = new AssertionError({
            actual: string,
            expected: regexp,
            message,
            operator: fnName,
            stackStartFn: fn
          });
          err.generatedMessage = generatedMessage;
          throw err;
        }
      }
      assert.match = function match(string, regexp, message) {
        internalMatch(string, regexp, message, match, "match");
      };
      assert.doesNotMatch = function doesNotMatch(string, regexp, message) {
        internalMatch(string, regexp, message, doesNotMatch, "doesNotMatch");
      };
      function strict() {
        for (var _len6 = arguments.length, args = new Array(_len6), _key6 = 0; _key6 < _len6; _key6++) {
          args[_key6] = arguments[_key6];
        }
        innerOk.apply(void 0, [strict, args.length].concat(args));
      }
      assert.strict = objectAssign(strict, assert, {
        equal: assert.strictEqual,
        deepEqual: assert.deepStrictEqual,
        notEqual: assert.notStrictEqual,
        notDeepEqual: assert.notDeepStrictEqual
      });
      assert.strict.strict = assert.strict;
    }
  });

  // node_modules/yosys2digitaljs/dist/core.js
  var require_core = __commonJS({
    "node_modules/yosys2digitaljs/dist/core.js"(exports) {
      "use strict";
      Object.defineProperty(exports, "__esModule", { value: true });
      exports.yosys2digitaljs = yosys2digitaljs;
      exports.io_ui = io_ui;
      exports.prepare_yosys_script = prepare_yosys_script;
      exports.prepare_verilator_args = prepare_verilator_args;
      var HashMap = require_hashmap();
      var bigInt = require_BigInteger();
      var _3vl_1 = require_dist();
      var topsort = require_topsort();
      function assert_fallback(val, msg) {
        if (!val)
          throw new Error(msg || "Assertion failed");
      }
      var isNodeEnvironment = typeof process !== "undefined" && process.versions != null && process.versions.node != null;
      var assert = isNodeEnvironment ? require_assert() : assert_fallback;
      var Yosys;
      (function(Yosys2) {
        Yosys2.ConstChars = ["0", "1", "x", "z"];
      })(Yosys || (Yosys = {}));
      var unary_gates = /* @__PURE__ */ new Set([
        "$repeater",
        "$not",
        "$neg",
        "$pos",
        "$reduce_and",
        "$reduce_nand",
        "$reduce_or",
        "$reduce_nor",
        "$reduce_xor",
        "$reduce_xnor",
        "$reduce_xnor",
        "$reduce_bool",
        "$logic_not"
      ]);
      var techmap_unary_gates = /* @__PURE__ */ new Set([
        "$_BUF_",
        "$_NOT_"
      ]);
      var binary_gates = /* @__PURE__ */ new Set([
        "$and",
        "$nand",
        "$or",
        "$nor",
        "$xor",
        "$xnor",
        "$add",
        "$sub",
        "$mul",
        "$div",
        "$mod",
        "$pow",
        "$lt",
        "$le",
        "$eq",
        "$ne",
        "$ge",
        "$gt",
        "$eqx",
        "$nex",
        "$shl",
        "$shr",
        "$sshl",
        "$sshr",
        "$shift",
        "$shiftx",
        "$logic_and",
        "$logic_or"
      ]);
      var techmap_binary_gates = /* @__PURE__ */ new Set([
        "$_AND_",
        "$_NAND_",
        "$_OR_",
        "$_NOR_",
        "$_XOR_",
        "$_XNOR_"
      ]);
      var gate_subst = /* @__PURE__ */ new Map([
        // Frontend cells (simlib.v)
        ["$not", "Not"],
        ["$and", "And"],
        ["$nand", "Nand"],
        ["$or", "Or"],
        ["$nor", "Nor"],
        ["$xor", "Xor"],
        ["$xnor", "Xnor"],
        ["$reduce_and", "AndReduce"],
        ["$reduce_nand", "NandReduce"],
        ["$reduce_or", "OrReduce"],
        ["$reduce_nor", "NorReduce"],
        ["$reduce_xor", "XorReduce"],
        ["$reduce_xnor", "XnorReduce"],
        ["$reduce_bool", "OrReduce"],
        ["$logic_not", "NorReduce"],
        ["$repeater", "Repeater"],
        ["$shl", "ShiftLeft"],
        ["$shr", "ShiftRight"],
        ["$lt", "Lt"],
        ["$le", "Le"],
        ["$eq", "Eq"],
        ["$ne", "Ne"],
        ["$gt", "Gt"],
        ["$ge", "Ge"],
        ["$constant", "Constant"],
        ["$neg", "Negation"],
        ["$pos", "UnaryPlus"],
        ["$add", "Addition"],
        ["$sub", "Subtraction"],
        ["$mul", "Multiplication"],
        ["$div", "Division"],
        ["$mod", "Modulo"],
        ["$pow", "Power"],
        ["$mux", "Mux"],
        ["$pmux", "Mux1Hot"],
        ["$mem", "Memory"],
        ["$mem_v2", "Memory"],
        ["$lut", "Memory"],
        ["$fsm", "FSM"],
        ["$clock", "Clock"],
        ["$button", "Button"],
        ["$lamp", "Lamp"],
        ["$numdisplay", "NumDisplay"],
        ["$numentry", "NumEntry"],
        ["$input", "Input"],
        ["$output", "Output"],
        ["$busgroup", "BusGroup"],
        ["$busungroup", "BusUngroup"],
        ["$busslice", "BusSlice"],
        ["$zeroextend", "ZeroExtend"],
        ["$signextend", "SignExtend"],
        ["$reduce_bool", "OrReduce"],
        ["$eqx", "Eq"],
        ["$nex", "Ne"],
        ["$sshl", "ShiftLeft"],
        ["$sshr", "ShiftRight"],
        ["$shift", "ShiftRight"],
        ["$shiftx", "ShiftRight"],
        ["$logic_and", "And"],
        ["$logic_or", "Or"],
        ["$dff", "Dff"],
        ["$dffe", "Dff"],
        ["$adff", "Dff"],
        ["$adffe", "Dff"],
        ["$sdff", "Dff"],
        ["$sdffe", "Dff"],
        ["$sdffce", "Dff"],
        ["$dlatch", "Dff"],
        ["$adlatch", "Dff"],
        ["$sr", "Dff"],
        ["$dffsr", "Dff"],
        ["$dffsre", "Dff"],
        ["$aldff", "Dff"],
        ["$aldffe", "Dff"],
        // Techmap cells (simcells.v)
        ["$_BUF_", "Repeater"],
        ["$_NOT_", "Not"],
        ["$_AND_", "And"],
        ["$_NAND_", "Nand"],
        ["$_OR_", "Or"],
        ["$_NOR_", "Nor"],
        ["$_XOR_", "Xor"],
        ["$_XNOR_", "Xnor"],
        ["$_MUX_", "Mux"]
      ]);
      var techmap_dff_kinds = /* @__PURE__ */ new Map([
        ["$_SR_", [["set", "clr"], ["out"]]],
        ["$_DFF_", [["clk"], ["in", "out"]]],
        ["$_DFFE_", [["clk", "en"], ["in", "out"]]],
        ["$_DFFSR_", [["clk", "set", "clr"], ["in", "out"]]],
        ["$_DFFSRE_", [["clk", "set", "clr", "en"], ["in", "out"]]],
        ["$_DFF_", [["clk", "arst"], ["in", "out"]]],
        ["$_DFFE_", [["clk", "arst", "en"], ["in", "out"]]],
        ["$_ALDFF_", [["clk", "aload"], ["in", "ain", "out"]]],
        ["$_ALDFFE_", [["clk", "aload", "en"], ["in", "ain", "out"]]],
        ["$_SDFF_", [["clk", "srst"], ["in", "out"]]],
        ["$_SDFFE_", [["clk", "srst", "en"], ["in", "out"]]],
        ["$_SDFFCE_", [["clk", "srst", "en"], ["in", "out"]]],
        ["$_DLATCH_", [["en"], ["in", "out"]]],
        ["$_ADLATCH_", [["en", "arst"], ["in", "out"]]],
        ["$_DLATCHSR_", [["en", "set", "clr"], ["in", "out"]]]
      ]);
      var techmap_dffs = /* @__PURE__ */ new Set();
      function techmap_names_for(name, ports) {
        return ports.flatMap((x) => x.endsWith("rst") ? [["N", "P"], ["0", "1"]] : [["N", "P"]]).reduce((a, b) => a.flatMap((d) => b.map((e) => [d, e].flat())), [[]]).map((x) => name + x.join("") + "_");
      }
      for (const [name, [ports, _]] of techmap_dff_kinds) {
        for (const s of techmap_names_for(name, ports)) {
          gate_subst.set(s, "Dff");
          techmap_dffs.add(s);
        }
      }
      var techmap_port_map = /* @__PURE__ */ new Map([
        ["set", "S"],
        ["clr", "R"],
        ["in", "D"],
        ["out", "Q"],
        ["clk", "C"],
        ["en", "E"],
        ["aload", "L"],
        ["ain", "AD"],
        ["arst", "R"],
        ["srst", "R"]
      ]);
      function port_to_polarity(port) {
        switch (port) {
          case "clk":
            return "clock";
          case "en":
            return "enable";
          default:
            return port;
        }
      }
      function module_deps(data) {
        const out = [];
        for (const [name, mod] of Object.entries(data.modules)) {
          out.push([name, 1 / 0]);
          for (const cname in mod.cells) {
            const cell = mod.cells[cname];
            if (cell.type in data.modules)
              out.push([cell.type, name]);
          }
        }
        return out;
      }
      function order_ports(data) {
        const unmap = { A: "in", Y: "out" };
        const binmap = { A: "in1", B: "in2", Y: "out" };
        const out = {
          "$mux": { A: "in0", B: "in1", S: "sel", Y: "out" },
          "$dff": { CLK: "clk", D: "in", Q: "out" },
          "$dffe": { CLK: "clk", EN: "en", D: "in", Q: "out" },
          "$adff": { CLK: "clk", ARST: "arst", D: "in", Q: "out" },
          "$adffe": { CLK: "clk", EN: "en", ARST: "arst", D: "in", Q: "out" },
          "$sdff": { CLK: "clk", SRST: "srst", D: "in", Q: "out" },
          "$sdffe": { CLK: "clk", EN: "en", SRST: "srst", D: "in", Q: "out" },
          "$sdffce": { CLK: "clk", EN: "en", SRST: "srst", D: "in", Q: "out" },
          "$dlatch": { EN: "en", D: "in", Q: "out" },
          "$adlatch": { EN: "en", ARST: "arst", D: "in", Q: "out" },
          "$dffsr": { CLK: "clk", SET: "set", CLR: "clr", D: "in", Q: "out" },
          "$dffsre": { CLK: "clk", EN: "en", SET: "set", CLR: "clr", D: "in", Q: "out" },
          "$aldff": { CLK: "clk", ALOAD: "aload", AD: "ain", D: "in", Q: "out" },
          "$aldffe": { CLK: "clk", EN: "en", ALOAD: "aload", AD: "ain", D: "in", Q: "out" },
          "$sr": { SET: "set", CLR: "clr", Q: "out" },
          "$fsm": { ARST: "arst", CLK: "clk", CTRL_IN: "in", CTRL_OUT: "out" },
          "$_MUX_": { A: "in0", B: "in1", S: "sel", Y: "out" }
        };
        binary_gates.forEach((nm) => out[nm] = binmap);
        techmap_binary_gates.forEach((nm) => out[nm] = binmap);
        unary_gates.forEach((nm) => out[nm] = unmap);
        techmap_unary_gates.forEach((nm) => out[nm] = unmap);
        for (const [name, [ports1, ports2]] of techmap_dff_kinds) {
          const portmap = {};
          for (const pname of ports1.concat(ports2)) {
            portmap[techmap_port_map.get(pname)] = pname;
          }
          for (const s of techmap_names_for(name, ports1)) {
            out[s] = portmap;
          }
        }
        for (const [name, mod] of Object.entries(data.modules)) {
          const portmap = {};
          const ins = [], outs = [];
          for (const pname in mod.ports) {
            portmap[pname] = pname;
          }
          out[name] = portmap;
        }
        return out;
      }
      function decode_json_bigint(param) {
        if (typeof param == "string")
          return bigInt(param, 2);
        else if (typeof param == "number")
          return bigInt(param);
        else
          assert(false);
      }
      function decode_json_number(param) {
        if (typeof param == "string")
          return Number.parseInt(param, 2);
        else if (typeof param == "number")
          return param;
        else
          assert(false);
      }
      function decode_json_bigint_as_array(param) {
        return decode_json_bigint(param).toArray(2).value;
      }
      function decode_json_constant(param, bits, fill = "0") {
        if (typeof param == "number")
          return bigInt(param).toArray(2).value.map(String).reverse().concat(Array(bits).fill(fill)).slice(0, bits).reverse().join("");
        else
          return param;
      }
      function parse_source_positions(str) {
        const ret = [];
        for (const entry of str.split("|")) {
          const colonIdx = entry.lastIndexOf(":");
          const name = entry.slice(0, colonIdx);
          const pos = entry.slice(colonIdx + 1);
          const [from, to] = pos.split("-").map((s) => s.split(".").map((v) => Number(v))).map(([line, column]) => ({ line, column }));
          ret.push({ name, from, to });
        }
        return ret;
      }
      function yosys_to_digitaljs(data, portmaps, options = {}) {
        const out = {};
        for (const [name, mod] of Object.entries(data.modules)) {
          out[name] = yosys_to_digitaljs_mod(name, mod, portmaps, options);
        }
        return out;
      }
      function yosys_to_digitaljs_mod(name, mod, portmaps, options = {}) {
        function constbit(bit) {
          return Yosys.ConstChars.includes(bit.toString());
        }
        const nets = new HashMap();
        const netnames = new HashMap();
        const netsrc = new HashMap();
        const bits = /* @__PURE__ */ new Map();
        const devnets = /* @__PURE__ */ new Map();
        let n = 0, pn = 0;
        function gen_name() {
          const nm = `dev${n++}`;
          devnets.set(nm, /* @__PURE__ */ new Map());
          return nm;
        }
        function gen_bitname() {
          return `bit${pn++}`;
        }
        function get_net(k) {
          if (!nets.has(k)) {
            const nms = netnames.get(k);
            const src = netsrc.get(k);
            nets.set(k, { source: void 0, targets: [], name: nms ? nms[0] : void 0, source_positions: src || [] });
          }
          return nets.get(k);
        }
        function add_net_source(k, d, p, primary = false) {
          if (k.length == 0)
            return;
          const net = get_net(k);
          if (net.source !== void 0) {
            throw Error("Multiple sources driving net: " + net.name);
          }
          net.source = { id: d, port: p };
          if (primary)
            for (const [nbit, bit] of k.entries()) {
              bits.set(bit, { id: d, port: p, num: nbit });
            }
          devnets.get(d).set(p, k);
        }
        function add_net_target(k, d, p) {
          if (k.length == 0)
            return;
          const net = get_net(k);
          net.targets.push({ id: d, port: p });
          devnets.get(d).set(p, k);
        }
        const mout = {
          devices: {},
          connectors: []
        };
        function add_device(dev) {
          const dname = gen_name();
          if (options.propagation !== void 0)
            dev.propagation = options.propagation;
          mout.devices[dname] = dev;
          return dname;
        }
        function add_busgroup(nbits, groups) {
          if (get_net(nbits).source !== void 0)
            return;
          const dname = add_device({
            type: "BusGroup",
            groups: groups.map((g) => g.length)
          });
          add_net_source(nbits, dname, "out");
          for (const [gn, group] of groups.entries()) {
            add_net_target(group, dname, "in" + gn);
          }
        }
        function connect_device(dname, cell, portmap) {
          const dirs = cell.port_directions || {};
          const pnames = Object.keys(cell.connections || {});
          for (const pname of pnames) {
            const pdir = dirs[pname] || "input";
            const pconn = cell.connections[pname];
            switch (pdir) {
              case "input":
              case "inout":
                add_net_target(pconn, dname, portmap[pname]);
                break;
              case "output":
                add_net_source(pconn, dname, portmap[pname], true);
                break;
              default:
                throw Error("Invalid port direction: " + pdir);
            }
          }
        }
        function connect_pmux(dname, cell) {
          add_net_target(cell.connections.A, dname, "in0");
          add_net_target(cell.connections.S.slice().reverse(), dname, "sel");
          add_net_source(cell.connections.Y, dname, "out", true);
          for (const i of Array(decode_json_number(cell.parameters.S_WIDTH)).keys()) {
            const p = (decode_json_number(cell.parameters.S_WIDTH) - i - 1) * decode_json_number(cell.parameters.WIDTH);
            add_net_target(cell.connections.B.slice(p, p + decode_json_number(cell.parameters.WIDTH)), dname, "in" + (i + 1));
          }
        }
        function connect_mem(dname, cell, dev) {
          for (const [k, port] of dev.rdports.entries()) {
            const portname = "rd" + k;
            add_net_target(cell.connections.RD_ADDR.slice(dev.abits * k, dev.abits * (k + 1)), dname, portname + "addr");
            add_net_source(cell.connections.RD_DATA.slice(dev.bits * k, dev.bits * (k + 1)), dname, portname + "data", true);
            if ("clock_polarity" in port)
              add_net_target([cell.connections.RD_CLK[k]], dname, portname + "clk");
            if ("enable_polarity" in port)
              add_net_target([cell.connections.RD_EN[k]], dname, portname + "en");
            if ("arst_polarity" in port)
              add_net_target([cell.connections.RD_ARST[k]], dname, portname + "arst");
            if ("srst_polarity" in port)
              add_net_target([cell.connections.RD_SRST[k]], dname, portname + "srst");
          }
          for (const [k, port] of dev.wrports.entries()) {
            const portname = "wr" + k;
            add_net_target(cell.connections.WR_ADDR.slice(dev.abits * k, dev.abits * (k + 1)), dname, portname + "addr");
            add_net_target(cell.connections.WR_DATA.slice(dev.bits * k, dev.bits * (k + 1)), dname, portname + "data");
            if ("clock_polarity" in port)
              add_net_target([cell.connections.WR_CLK[k]], dname, portname + "clk");
            if ("enable_polarity" in port) {
              if (port.no_bit_enable)
                add_net_target([cell.connections.WR_EN[dev.bits * k]], dname, portname + "en");
              else
                add_net_target(cell.connections.WR_EN.slice(dev.bits * k, dev.bits * (k + 1)), dname, portname + "en");
            }
          }
        }
        for (const [nname, data] of Object.entries(mod.netnames)) {
          if (data.hide_name)
            continue;
          let l = netnames.get(data.bits);
          if (l === void 0) {
            l = [];
            netnames.set(data.bits, l);
          }
          l.push(nname);
          if (typeof data.attributes == "object" && data.attributes.src) {
            let l2 = netsrc.get(data.bits);
            if (l2 === void 0) {
              l2 = [];
              netsrc.set(data.bits, l2);
            }
            const positions = parse_source_positions(data.attributes.src);
            l2.push(...positions);
          }
        }
        for (const [pname, port] of Object.entries(mod.ports)) {
          if (!port || !port.bits) continue;
          const dir = port.direction == "input" ? "Input" : port.direction == "output" ? "Output" : void 0;
          if (!dir) continue;
          const dname = add_device({
            type: dir,
            net: pname,
            order: n,
            bits: port.bits.length
          });
          switch (port.direction) {
            case "input":
              add_net_source(port.bits, dname, "out", true);
              break;
            case "output":
              add_net_target(port.bits, dname, "in");
              break;
            default:
              throw Error("Invalid port direction: " + port.direction);
          }
        }
        for (const [cname, cell] of Object.entries(mod.cells)) {
          let match_port = function(con, nsig, sz) {
            const sig = decode_json_number(nsig);
            if (con.length > sz)
              con.splice(sz);
            else if (con.length < sz) {
              const ccon = con.slice();
              const pad = sig ? con.slice(-1)[0] : "0";
              con.splice(con.length, 0, ...Array(sz - con.length).fill(pad));
              if (!con.every(constbit) && get_net(con).source === void 0) {
                const extname = add_device({
                  type: sig ? "SignExtend" : "ZeroExtend",
                  extend: { input: ccon.length, output: con.length }
                });
                add_net_target(ccon, extname, "in");
                add_net_source(con, extname, "out");
              }
            }
          }, zero_extend_output = function(con) {
            if (con.length > 1) {
              const ccon = con.slice();
              con.splice(1);
              const extname = add_device({
                type: "ZeroExtend",
                extend: { input: con.length, output: ccon.length }
              });
              add_net_source(ccon, extname, "out");
              add_net_target(con, extname, "in");
            }
          };
          const dev = {
            label: cname,
            type: gate_subst.get(cell.type)
          };
          if (cell.hide_name)
            dev.hide_label = true;
          if (dev.type == void 0) {
            dev.type = "Subcircuit";
            dev.celltype = cell.type;
          }
          if (typeof cell.attributes == "object" && cell.attributes.src) {
            dev.source_positions = parse_source_positions(cell.attributes.src);
          }
          const dname = add_device(dev);
          if (unary_gates.has(cell.type)) {
            assert(cell.connections.A.length == decode_json_number(cell.parameters.A_WIDTH));
            assert(cell.connections.Y.length == decode_json_number(cell.parameters.Y_WIDTH));
            assert(cell.port_directions.A == "input");
            assert(cell.port_directions.Y == "output");
          }
          if (techmap_unary_gates.has(cell.type)) {
            assert(cell.connections.A.length == 1);
            assert(cell.connections.Y.length == 1);
            assert(cell.port_directions.A == "input");
            assert(cell.port_directions.Y == "output");
          }
          if (binary_gates.has(cell.type)) {
            assert(cell.connections.A.length == decode_json_number(cell.parameters.A_WIDTH));
            assert(cell.connections.B.length == decode_json_number(cell.parameters.B_WIDTH));
            assert(cell.connections.Y.length == decode_json_number(cell.parameters.Y_WIDTH));
            assert(cell.port_directions.A == "input");
            assert(cell.port_directions.B == "input");
            assert(cell.port_directions.Y == "output");
          }
          if (techmap_binary_gates.has(cell.type)) {
            assert(cell.connections.A.length == 1);
            assert(cell.connections.B.length == 1);
            assert(cell.connections.Y.length == 1);
            assert(cell.port_directions.A == "input");
            assert(cell.port_directions.B == "input");
            assert(cell.port_directions.Y == "output");
          }
          if (["$dff", "$dffe", "$adff", "$adffe", "$sdff", "$sdffe", "$sdffce", "$dlatch", "$adlatch", "$dffsr", "$dffsre", "$aldff", "$aldffe"].includes(cell.type)) {
            assert(cell.connections.D.length == decode_json_number(cell.parameters.WIDTH));
            assert(cell.connections.Q.length == decode_json_number(cell.parameters.WIDTH));
            assert(cell.port_directions.D == "input");
            assert(cell.port_directions.Q == "output");
            if (cell.type != "$dlatch" && cell.type != "$adlatch") {
              assert(cell.connections.CLK.length == 1);
              assert(cell.port_directions.CLK == "input");
            }
          }
          if (["$dffe", "$adffe", "$sdffe", "$sdffce", "$dffsre", "$aldffe", "$dlatch", "$adlatch"].includes(cell.type)) {
            assert(cell.connections.EN.length == 1);
            assert(cell.port_directions.EN == "input");
          }
          if (["$adff", "$adffe", "$adlatch"].includes(cell.type)) {
            assert(cell.connections.ARST.length == 1);
            assert(cell.port_directions.ARST == "input");
          }
          if (["$sdff", "$sdffe", "$sdffce"].includes(cell.type)) {
            assert(cell.connections.SRST.length == 1);
            assert(cell.port_directions.SRST == "input");
          }
          if (["$dffsr", "$dffsre"].includes(cell.type)) {
            assert(cell.connections.SET.length == decode_json_number(cell.parameters.WIDTH));
            assert(cell.connections.CLR.length == decode_json_number(cell.parameters.WIDTH));
            assert(cell.port_directions.SET == "input");
            assert(cell.port_directions.CLR == "input");
          }
          if (techmap_dffs.has(cell.type)) {
            const prefix = cell.type.match(/^[^_]*_[^_]*_/)[0];
            const params = [...cell.type.split("_")[2]];
            const [ports1, ports2] = techmap_dff_kinds.get(prefix);
            for (const port of ports1.concat(ports2)) {
              const mport = techmap_port_map.get(port);
              assert(cell.connections[mport].length == 1);
              assert(cell.port_directions[mport] == (mport == "Q" ? "output" : "input"));
            }
            dev.bits = 1;
            dev.polarity = {};
            for (const port of ports1) {
              const pol = params.shift();
              switch (pol) {
                case "P":
                  dev.polarity[port_to_polarity(port)] = true;
                  break;
                case "N":
                  dev.polarity[port_to_polarity(port)] = false;
                  break;
                default:
                  throw Error("Invalid polarity char " + pol);
              }
              if (port.endsWith("rst")) {
                dev[port + "_value"] = String(params.shift());
              }
            }
            assert(params.length == 0);
            if (!ports2.includes("in"))
              dev.no_data = true;
            if (prefix == "$_SDFFCE_")
              dev.enable_srst = true;
          }
          switch (cell.type) {
            case "$neg":
            case "$pos":
              dev.bits = {
                in: cell.connections.A.length,
                out: cell.connections.Y.length
              };
              dev.signed = Boolean(decode_json_number(cell.parameters.A_SIGNED));
              break;
            case "$not":
              match_port(cell.connections.A, cell.parameters.A_SIGNED, cell.connections.Y.length);
              dev.bits = cell.connections.Y.length;
              break;
            case "$add":
            case "$sub":
            case "$mul":
            case "$div":
            case "$mod":
            case "$pow":
              dev.bits = {
                in1: cell.connections.A.length,
                in2: cell.connections.B.length,
                out: cell.connections.Y.length
              };
              dev.signed = {
                in1: Boolean(decode_json_number(cell.parameters.A_SIGNED)),
                in2: Boolean(decode_json_number(cell.parameters.B_SIGNED))
              };
              break;
            case "$and":
            case "$nand":
            case "$or":
            case "$nor":
            case "$xor":
            case "$xnor":
              match_port(cell.connections.A, cell.parameters.A_SIGNED, cell.connections.Y.length);
              match_port(cell.connections.B, cell.parameters.B_SIGNED, cell.connections.Y.length);
              dev.bits = cell.connections.Y.length;
              break;
            case "$reduce_and":
            case "$reduce_or":
            case "$reduce_xor":
            case "$reduce_xnor":
            case "$reduce_bool":
            case "$logic_not":
              dev.bits = cell.connections.A.length;
              zero_extend_output(cell.connections.Y);
              if (dev.bits == 1) {
                if (["$reduce_xnor", "$logic_not"].includes(cell.type))
                  dev.type = "Not";
                else
                  dev.type = "Repeater";
              }
              break;
            case "$eq":
            case "$ne":
            case "$lt":
            case "$le":
            case "$gt":
            case "$ge":
            case "$eqx":
            case "$nex":
              dev.bits = {
                in1: cell.connections.A.length,
                in2: cell.connections.B.length
              };
              dev.signed = {
                in1: Boolean(decode_json_number(cell.parameters.A_SIGNED)),
                in2: Boolean(decode_json_number(cell.parameters.B_SIGNED))
              };
              zero_extend_output(cell.connections.Y);
              break;
            case "$shl":
            case "$shr":
            case "$sshl":
            case "$sshr":
            case "$shift":
            case "$shiftx":
              dev.bits = {
                in1: cell.connections.A.length,
                in2: cell.connections.B.length,
                out: cell.connections.Y.length
              };
              dev.signed = {
                in1: Boolean(decode_json_number(cell.parameters.A_SIGNED)),
                in2: Boolean(decode_json_number(cell.parameters.B_SIGNED) && ["$shift", "$shiftx"].includes(cell.type)),
                out: Boolean(decode_json_number(cell.parameters.A_SIGNED) && ["$sshl", "$sshr"].includes(cell.type))
              };
              dev.fillx = cell.type == "$shiftx";
              break;
            case "$logic_and":
            case "$logic_or": {
              let reduce_input = function(con) {
                const ccon = con.slice();
                con.splice(0, con.length, gen_bitname());
                const extname = add_device({
                  type: "OrReduce",
                  bits: ccon.length
                });
                add_net_source(con, extname, "out");
                add_net_target(ccon, extname, "in");
              };
              if (cell.connections.A.length > 1)
                reduce_input(cell.connections.A);
              if (cell.connections.B.length > 1)
                reduce_input(cell.connections.B);
              zero_extend_output(cell.connections.Y);
              break;
            }
            case "$mux":
              assert(cell.connections.A.length == decode_json_number(cell.parameters.WIDTH));
              assert(cell.connections.B.length == decode_json_number(cell.parameters.WIDTH));
              assert(cell.connections.Y.length == decode_json_number(cell.parameters.WIDTH));
              assert(cell.port_directions.A == "input");
              assert(cell.port_directions.B == "input");
              assert(cell.port_directions.Y == "output");
              dev.bits = {
                in: decode_json_number(cell.parameters.WIDTH),
                sel: 1
              };
              break;
            case "$pmux":
              assert(cell.connections.B.length == decode_json_number(cell.parameters.WIDTH) * decode_json_number(cell.parameters.S_WIDTH));
              assert(cell.connections.A.length == decode_json_number(cell.parameters.WIDTH));
              assert(cell.connections.S.length == decode_json_number(cell.parameters.S_WIDTH));
              assert(cell.connections.Y.length == decode_json_number(cell.parameters.WIDTH));
              assert(cell.port_directions.A == "input");
              assert(cell.port_directions.B == "input");
              assert(cell.port_directions.S == "input");
              assert(cell.port_directions.Y == "output");
              dev.bits = {
                in: decode_json_number(cell.parameters.WIDTH),
                sel: decode_json_number(cell.parameters.S_WIDTH)
              };
              break;
            case "$dff":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY))
              };
              break;
            case "$dffe":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY)),
                enable: Boolean(decode_json_number(cell.parameters.EN_POLARITY))
              };
              break;
            case "$aldff":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY)),
                aload: Boolean(decode_json_number(cell.parameters.ALOAD_POLARITY))
              };
              break;
            case "$aldffe":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY)),
                enable: Boolean(decode_json_number(cell.parameters.EN_POLARITY)),
                aload: Boolean(decode_json_number(cell.parameters.ALOAD_POLARITY))
              };
              break;
            case "$adff":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY)),
                arst: Boolean(decode_json_number(cell.parameters.ARST_POLARITY))
              };
              dev.arst_value = decode_json_constant(cell.parameters.ARST_VALUE, dev.bits);
              break;
            case "$sdff":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY)),
                srst: Boolean(decode_json_number(cell.parameters.SRST_POLARITY))
              };
              dev.srst_value = decode_json_constant(cell.parameters.SRST_VALUE, dev.bits);
              break;
            case "$adffe":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY)),
                arst: Boolean(decode_json_number(cell.parameters.ARST_POLARITY)),
                enable: Boolean(decode_json_number(cell.parameters.EN_POLARITY))
              };
              dev.arst_value = decode_json_constant(cell.parameters.ARST_VALUE, dev.bits);
              break;
            case "$sdffe":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY)),
                srst: Boolean(decode_json_number(cell.parameters.SRST_POLARITY)),
                enable: Boolean(decode_json_number(cell.parameters.EN_POLARITY))
              };
              dev.srst_value = decode_json_constant(cell.parameters.SRST_VALUE, dev.bits);
              break;
            case "$sdffce":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY)),
                srst: Boolean(decode_json_number(cell.parameters.SRST_POLARITY)),
                enable: Boolean(decode_json_number(cell.parameters.EN_POLARITY))
              };
              dev.enable_srst = true;
              dev.srst_value = decode_json_constant(cell.parameters.SRST_VALUE, dev.bits);
              break;
            case "$dlatch":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                enable: Boolean(decode_json_number(cell.parameters.EN_POLARITY))
              };
              break;
            case "$adlatch":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                enable: Boolean(decode_json_number(cell.parameters.EN_POLARITY)),
                arst: Boolean(decode_json_number(cell.parameters.ARST_POLARITY))
              };
              dev.arst_value = decode_json_constant(cell.parameters.ARST_VALUE, dev.bits);
              break;
            case "$dffsr":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY)),
                set: Boolean(decode_json_number(cell.parameters.SET_POLARITY)),
                clr: Boolean(decode_json_number(cell.parameters.CLR_POLARITY))
              };
              break;
            case "$dffsre":
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY)),
                enable: Boolean(decode_json_number(cell.parameters.EN_POLARITY)),
                set: Boolean(decode_json_number(cell.parameters.SET_POLARITY)),
                clr: Boolean(decode_json_number(cell.parameters.CLR_POLARITY))
              };
              break;
            case "$sr":
              assert(cell.connections.Q.length == decode_json_number(cell.parameters.WIDTH));
              assert(cell.port_directions.Q == "output");
              dev.no_data = true;
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.polarity = {
                set: Boolean(decode_json_number(cell.parameters.SET_POLARITY)),
                clr: Boolean(decode_json_number(cell.parameters.CLR_POLARITY))
              };
              break;
            case "$fsm": {
              assert(cell.connections.ARST.length == 1);
              assert(cell.connections.CLK.length == 1);
              assert(cell.connections.CTRL_IN.length == decode_json_number(cell.parameters.CTRL_IN_WIDTH));
              assert(cell.connections.CTRL_OUT.length == decode_json_number(cell.parameters.CTRL_OUT_WIDTH));
              const TRANS_NUM = decode_json_number(cell.parameters.TRANS_NUM);
              const STATE_NUM_LOG2 = decode_json_number(cell.parameters.STATE_NUM_LOG2);
              const step = 2 * STATE_NUM_LOG2 + decode_json_number(cell.parameters.CTRL_IN_WIDTH) + decode_json_number(cell.parameters.CTRL_OUT_WIDTH);
              const tt = typeof cell.parameters.TRANS_TABLE == "number" ? _3vl_1.Vector3vl.fromBin(bigInt(cell.parameters.TRANS_TABLE).toString(2), TRANS_NUM * step).toBin() : cell.parameters.TRANS_TABLE;
              assert(tt.length == TRANS_NUM * step);
              dev.polarity = {
                clock: Boolean(decode_json_number(cell.parameters.CLK_POLARITY)),
                arst: Boolean(decode_json_number(cell.parameters.ARST_POLARITY))
              };
              dev.wirename = cell.parameters.NAME;
              dev.bits = {
                in: decode_json_number(cell.parameters.CTRL_IN_WIDTH),
                out: decode_json_number(cell.parameters.CTRL_OUT_WIDTH)
              };
              dev.states = decode_json_number(cell.parameters.STATE_NUM);
              dev.init_state = decode_json_number(cell.parameters.STATE_RST);
              dev.trans_table = [];
              for (let i = 0; i < TRANS_NUM; i++) {
                let base = i * step;
                const f = (sz) => {
                  const ret = tt.slice(base, base + sz);
                  base += sz;
                  return ret;
                };
                const o = {
                  state_in: parseInt(f(STATE_NUM_LOG2), 2),
                  ctrl_in: f(decode_json_number(cell.parameters.CTRL_IN_WIDTH)).replace(/-/g, "x"),
                  state_out: parseInt(f(STATE_NUM_LOG2), 2),
                  ctrl_out: f(decode_json_number(cell.parameters.CTRL_OUT_WIDTH))
                };
                dev.trans_table.push(o);
              }
              break;
            }
            case "$mem":
            case "$mem_v2": {
              const RD_PORTS = decode_json_number(cell.parameters.RD_PORTS);
              const WR_PORTS = decode_json_number(cell.parameters.WR_PORTS);
              assert(cell.connections.RD_EN.length == RD_PORTS);
              assert(cell.connections.RD_CLK.length == RD_PORTS);
              assert(cell.connections.RD_DATA.length == RD_PORTS * decode_json_number(cell.parameters.WIDTH));
              assert(cell.connections.RD_ADDR.length == RD_PORTS * decode_json_number(cell.parameters.ABITS));
              assert(cell.connections.WR_EN.length == WR_PORTS * decode_json_number(cell.parameters.WIDTH));
              assert(cell.connections.WR_CLK.length == WR_PORTS);
              assert(cell.connections.WR_DATA.length == WR_PORTS * decode_json_number(cell.parameters.WIDTH));
              assert(cell.connections.WR_ADDR.length == WR_PORTS * decode_json_number(cell.parameters.ABITS));
              if (cell.type == "$mem_v2") {
                assert(cell.connections.RD_ARST.length == RD_PORTS);
                assert(cell.connections.RD_SRST.length == RD_PORTS);
              }
              dev.bits = decode_json_number(cell.parameters.WIDTH);
              dev.abits = decode_json_number(cell.parameters.ABITS);
              dev.words = decode_json_number(cell.parameters.SIZE);
              dev.offset = decode_json_number(cell.parameters.OFFSET);
              dev.rdports = [];
              dev.wrports = [];
              const rdpol = decode_json_bigint_as_array(cell.parameters.RD_CLK_POLARITY).reverse();
              const rden = decode_json_bigint_as_array(cell.parameters.RD_CLK_ENABLE).reverse();
              const rdtr = cell.type == "$mem_v2" ? [] : decode_json_bigint_as_array(cell.parameters.RD_TRANSPARENT).reverse();
              const wrpol = decode_json_bigint_as_array(cell.parameters.WR_CLK_POLARITY).reverse();
              const wren = decode_json_bigint_as_array(cell.parameters.WR_CLK_ENABLE).reverse();
              const init = typeof cell.parameters.INIT == "number" ? bigInt(cell.parameters.INIT).toArray(2).value.map(String).reverse() : cell.parameters.INIT.split("").reverse();
              const v2_feature = (param) => cell.type == "$mem_v2" ? decode_json_bigint_as_array(param).reverse() : [];
              const v2_feature_const = (param, size) => cell.type == "$mem_v2" ? decode_json_constant(param, size) : "";
              const rdtrmask = v2_feature(cell.parameters.RD_TRANSPARENCY_MASK);
              const rdcolmask = v2_feature(cell.parameters.RD_COLLISION_X_MASK);
              const rdensrst = v2_feature(cell.parameters.RD_CE_OVER_SRST);
              const rdinit = v2_feature_const(cell.parameters.RD_INIT_VALUE, dev.bits * RD_PORTS);
              const rdarst = v2_feature_const(cell.parameters.RD_ARST_VALUE, dev.bits * RD_PORTS);
              const rdsrst = v2_feature_const(cell.parameters.RD_SRST_VALUE, dev.bits * RD_PORTS);
              if (cell.parameters.INIT) {
                const l = init.slice(-1)[0] == "x" ? "x" : "0";
                const memdata = new _3vl_1.Mem3vl(dev.bits, dev.words);
                for (const k of Array(dev.words).keys()) {
                  const wrd = init.slice(dev.bits * k, dev.bits * (k + 1));
                  while (wrd.length < dev.bits)
                    wrd.push(l);
                  memdata.set(k, _3vl_1.Vector3vl.fromBin(wrd.reverse().join("")));
                }
                dev.memdata = memdata.toJSON();
              }
              for (const k of Array(RD_PORTS).keys()) {
                const port = {};
                if (rden[k]) {
                  port.clock_polarity = Boolean(rdpol[k]);
                  if (cell.connections.RD_EN[k] != "1")
                    port.enable_polarity = true;
                }
                ;
                if (rdtr[k])
                  port.transparent = true;
                if (cell.type == "$mem_v2") {
                  let mk_init = function(s, f) {
                    const v = s.slice(dev.bits * k, dev.bits * (k + 1));
                    if (!v.split("").every((c) => c == "x"))
                      f(v);
                  }, mk_mask = function(s, f) {
                    const v = Array(WR_PORTS).fill(0);
                    s.slice(WR_PORTS * k, WR_PORTS * (k + 1)).map((c, i) => {
                      v[i] = c;
                    });
                    if (v.every((c) => c))
                      f(true);
                    else if (v.some((c) => c))
                      f(v.map((c) => Boolean(c)));
                  };
                  if (rdensrst[k])
                    port.enable_srst = true;
                  ;
                  mk_init(rdinit, (v) => port.init_value = v);
                  if (cell.connections.RD_ARST[k] != "0") {
                    port.arst_polarity = true;
                    mk_init(rdarst, (v) => port.arst_value = v);
                  }
                  if (cell.connections.RD_SRST[k] != "0") {
                    port.srst_polarity = true;
                    mk_init(rdsrst, (v) => port.srst_value = v);
                  }
                  mk_mask(rdtrmask, (v) => port.transparent = v);
                  mk_mask(rdcolmask, (v) => port.collision = v);
                }
                dev.rdports.push(port);
              }
              for (const k of Array(WR_PORTS).keys()) {
                const port = {};
                if (wren[k]) {
                  port.clock_polarity = Boolean(wrpol[k]);
                  const wr_en_connections = cell.connections.WR_EN.slice(dev.bits * k, dev.bits * (k + 1));
                  if (wr_en_connections.some((z) => z != "1")) {
                    port.enable_polarity = true;
                    if (wr_en_connections.every((z) => z == wr_en_connections[0]))
                      port.no_bit_enable = true;
                  }
                }
                ;
                dev.wrports.push(port);
              }
              break;
            }
            case "$lut":
              assert(cell.connections.A.length == decode_json_number(cell.parameters.WIDTH));
              assert(cell.connections.Y.length == 1);
              assert(cell.port_directions.A == "input");
              assert(cell.port_directions.Y == "output");
              dev.abits = cell.connections.A.length;
              dev.bits = cell.connections.Y.length;
              dev.rdports = [{}];
              dev.wrports = [];
              dev.memdata = cell.parameters.LUT.split("").reverse();
              assert(dev.memdata.length == Math.pow(2, dev.abits));
              cell.connections.RD_ADDR = cell.connections.A;
              cell.connections.RD_DATA = cell.connections.Y;
              delete cell.connections.A;
              delete cell.connections.Y;
              break;
            default:
          }
          if (dev.type == "Dff") {
            const nms = netnames.get(cell.connections.Q);
            if (nms !== void 0) {
              for (const nm of nms) {
                if (mod.netnames[nm].attributes.init !== void 0)
                  dev.initial = decode_json_constant(mod.netnames[nm].attributes.init, dev.bits);
              }
            }
          }
          const portmap = portmaps[cell.type];
          if (portmap)
            connect_device(dname, cell, portmap);
          else if (cell.type == "$pmux")
            connect_pmux(dname, cell);
          else if (cell.type == "$mem")
            connect_mem(dname, cell, dev);
          else if (cell.type == "$mem_v2")
            connect_mem(dname, cell, dev);
          else if (cell.type == "$lut")
            connect_mem(dname, cell, dev);
          else {
            const dynamic_portmap = {};
            const dirs = cell.port_directions || {};
            for (const pname of Object.keys(cell.connections || {})) {
              const pdir = dirs[pname] || "input";
              dynamic_portmap[pname] = pdir == "input" || pdir == "inout" || pdir == "in" ? { in: pname } : { out: pname };
            }
            dev.type = "Subcircuit";
            dev.celltype = cell.type;
            connect_device(dname, cell, dynamic_portmap);
          }
        }
        for (const [nbits, net] of nets.entries()) {
          if (net.source !== void 0)
            continue;
          const groups = [[]];
          let pbitinfo = void 0;
          for (const bit of nbits) {
            let bitinfo = bits.get(bit);
            if (bitinfo == void 0 && constbit(bit))
              bitinfo = "const";
            if (groups.slice(-1)[0].length > 0 && (typeof bitinfo != typeof pbitinfo || typeof bitinfo == "object" && typeof pbitinfo == "object" && (bitinfo.id != pbitinfo.id || bitinfo.port != pbitinfo.port || bitinfo.num != pbitinfo.num + 1))) {
              groups.push([]);
            }
            groups.slice(-1)[0].push(bit);
            pbitinfo = bitinfo;
          }
          if (groups.length == 1)
            continue;
          if (groups.slice(-1)[0].every((x) => x == "0")) {
            const ilen = nbits.length - groups.slice(-1)[0].length;
            const dname = add_device({
              type: "ZeroExtend",
              extend: { output: nbits.length, input: ilen }
            });
            const zbits = nbits.slice(0, ilen);
            add_net_source(nbits, dname, "out");
            add_net_target(zbits, dname, "in");
            if (groups.length > 2)
              add_busgroup(zbits, groups.slice(0, groups.length - 1));
          } else
            add_busgroup(nbits, groups);
        }
        for (const [nbits, net] of nets.entries()) {
          if (net.source !== void 0)
            continue;
          if (!nbits.every(constbit))
            continue;
          const dname = add_device({
            //            label: String(val), // TODO
            type: "Constant",
            constant: nbits.slice().reverse().join("")
          });
          add_net_source(nbits, dname, "out");
        }
        for (const [nbits, net] of nets.entries()) {
          if (net.source !== void 0)
            continue;
          assert(nbits.every((x) => constbit(x) || typeof x == "number" && x > 1));
          const bitinfos = nbits.map((x) => bits.get(x));
          if (!bitinfos.every((x) => typeof x == "object"))
            continue;
          assert(bitinfos.every((info) => info.id == bitinfos[0].id && info.port == bitinfos[0].port));
          const cconn = devnets.get(bitinfos[0].id).get(bitinfos[0].port);
          const dname = add_device({
            type: "BusSlice",
            slice: {
              first: bitinfos[0].num,
              count: bitinfos.length,
              total: cconn.length
            }
          });
          add_net_source(nbits, dname, "out");
          add_net_target(cconn, dname, "in");
        }
        for (const [nbits, net] of nets.entries()) {
          if (net.source === void 0) {
            console.warn("Undriven net in " + name + ": " + nbits);
            continue;
          }
          let first = true;
          for (const target in net.targets) {
            const conn = {
              to: net.targets[target],
              from: net.source
            };
            if (net.name)
              conn.name = net.name;
            if (net.source_positions)
              conn.source_positions = net.source_positions;
            if (!first && mout.devices[conn.from.id].type == "Constant") {
              const dname = add_device({
                type: "Constant",
                constant: mout.devices[conn.from.id].constant
              });
              conn.from = { id: dname, port: "out" };
            }
            mout.connectors.push(conn);
            first = false;
          }
        }
        return mout;
      }
      function yosys2digitaljs(obj, options = {}) {
        const portmaps = order_ports(obj);
        const out = yosys_to_digitaljs(obj, portmaps, options);
        const toporder = topsort(module_deps(obj));
        toporder.pop();
        const toplevel = toporder.pop();
        const output = Object.assign({ subcircuits: {} }, out[toplevel]);
        for (const x of toporder)
          output.subcircuits[x] = out[x];
        return output;
      }
      function io_ui(output) {
        for (const [name, dev] of Object.entries(output.devices)) {
          if (dev.type == "Input" || dev.type == "Output") {
            dev.label = dev.net;
          }
          if (dev.type == "Input" && dev.bits == 1 && (dev.label == "clk" || dev.label == "clock")) {
            dev.type = "Clock";
            dev.propagation = 100;
          }
          if (dev.type == "Input")
            dev.type = dev.bits == 1 ? "Button" : "NumEntry";
          if (dev.type == "Output") {
            if (dev.bits == 1)
              dev.type = "Lamp";
            else if (dev.bits == 8 && (dev.label == "display7" || dev.label.startsWith("display7_")))
              dev.type = "Display7";
            else
              dev.type = "NumDisplay";
          }
        }
      }
      function ansi_c_escape_contents(cmd) {
        function func(ch) {
          if (ch == "	")
            return "\\t";
          if (ch == "\r")
            return "\\r";
          if (ch == "\n")
            return "\\n";
          return "\\x" + ch.charCodeAt(0).toString(16).padStart(2, "0");
        }
        return cmd.replace(/(["'\\])/g, "\\$1").replace(/[\x00-\x1F\x7F-\x9F]/g, func);
      }
      function ansi_c_escape(cmd) {
        return '"' + ansi_c_escape_contents(cmd) + '"';
      }
      function shell_escape_contents(cmd) {
        return cmd.replace(/(["\r\n$`\\])/g, "\\$1");
      }
      function shell_escape(cmd) {
        return '"' + shell_escape_contents(cmd) + '"';
      }
      function process_filename(filename) {
        var _a;
        const ext = (_a = filename.match(/\.[a-z]+$/)) === null || _a === void 0 ? void 0 : _a[0];
        const commands = {
          ".il": "read_rtlil",
          ".sv": "read_verilog -sv",
          ".v": "read_verilog"
        };
        if (ext && ext in commands) {
          return `${commands[ext]} ${ansi_c_escape(filename)}`;
        } else {
          return "";
        }
      }
      function prepare_yosys_script(filenames, options) {
        const optimize_simp = options.optimize ? "opt" : "opt_clean";
        const optimize = options.optimize ? "opt -full" : "opt_clean";
        const fsmexpand = options.fsmexpand ? " -expand" : "";
        const fsmpass = options.fsm == "nomap" ? "fsm -nomap" + fsmexpand : options.fsm ? "fsm" + fsmexpand : "";
        const techmap = options.techmap ? "techmap" : "";
        const abc = !options.abc ? "" : options.abc.type == "gates" ? "abc -g " + options.abc.kinds.join(",") : options.abc.type == "lut" ? "abc -lut " + options.abc.width : "";
        const readFilesScript = filenames.map((filename) => process_filename(filename)).map((cmd) => isNodeEnvironment ? shell_escape_contents(cmd) : cmd);
        const yosysScript = [...readFilesScript, "setattr -mod -unset top", "hierarchy -auto-top", "proc", optimize_simp, fsmpass, "memory -nomap", "wreduce -memx", optimize, techmap, optimize, abc];
        return yosysScript.join("; ");
      }
      function prepare_verilator_args(filenames) {
        filenames = filenames.filter((n) => /\.(v|sv)$/.test(n));
        const processed_filenames = isNodeEnvironment ? filenames.map(shell_escape) : filenames;
        return ["-lint-only", "-Wall", "-Wno-DECLFILENAME", "-Wno-UNOPT", "-Wno-UNOPTFLAT", ...processed_filenames];
      }
    }
  });

  // bridge.js
  var require_bridge = __commonJS({
    "bridge.js"() {
      var y2d = require_core();
      window.processYosys = y2d.yosys2digitaljs;
    }
  });
  require_bridge();
})();
/*! Bundled license information:

assert/build/internal/util/comparisons.js:
  (*!
   * The buffer module from node.js, for the browser.
   *
   * @author   Feross Aboukhadijeh <feross@feross.org> <http://feross.org>
   * @license  MIT
   *)
*/
