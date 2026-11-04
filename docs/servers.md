# Анализ серверной сети Deadlock

Источник: [Valve SDR API, App ID 1422450](https://api.steampowered.com/ISteamApps/GetSDRConfig/v1/?appid=1422450).

Снимок получен 03.11.2026; ревизия 1793736599. Доступно 33 точек с IPv4 relay. Объекты pops без relays исключены.

Это список ретрансляторов, а не всех физических матчевых серверов или пулов игроков. Российских и материковых китайских relay в снимке нет.

| Код | Название Valve | Группа | IPv4 |
|---|---|---|---:|
| ams | Amsterdam (Netherlands) | EU | 4 |
| dfra | Datapacket Frankfurt (Germany) | EU | 2 |
| dlhr | Datapacket London (England) | EU | 2 |
| dvie | Datapacket Vienna (Austria) | EU | 2 |
| fra | Frankfurt (Germany) | EU | 16 |
| lhr | London (England) | EU | 4 |
| mad | Madrid (Spain) | EU | 4 |
| par | Paris (France) | EU | 4 |
| vie | Vienna (Austria) | EU | 6 |
| waw | Warsaw (Poland) | EU | 6 |
| sto2 | Stockholm - Bromma (Sweden) | EU / Север | 10 |
| sto | Stockholm - Kista (Sweden) | EU / Север | 11 |
| atl | Atlanta (Georgia) | US | 4 |
| ord | Chicago (Illinois) | US | 4 |
| dfw | Dallas (Texas) | US | 4 |
| lax | Los Angeles (California) | US | 4 |
| sea | Seattle (Washington) | US | 2 |
| iad | Sterling (Virginia) | US | 4 |
| maa2 | Chennai - Ambattur (India) | Азия / прочие | 2 |
| dfjr | Datapacket Fujairah (UAE) | Азия / прочие | 2 |
| dxb | Dubai (United Arab Emirates) | Азия / прочие | 2 |
| gum | Guam | Азия / прочие | 2 |
| bom2 | Mumbai (India) | Азия / прочие | 2 |
| seo | Seoul (South Korea) | Азия / прочие | 4 |
| sgp | Singapore | Азия / прочие | 6 |
| tyo | Tokyo Koto City (Japan) | Азия / прочие | 6 |
| jnb | Johannesburg (South Africa) | Африка | 2 |
| hkg | Hong Kong | Китай / HK | 10 |
| syd | Sydney (Australia) | Океания | 4 |
| eze | Buenos Aires (Argentina) | Южная Америка | 4 |
| lim | Lima (Peru) | Южная Америка | 4 |
| scl | Santiago (Chile) | Южная Америка | 2 |
| gru | Sao Paulo (Brazil) | Южная Америка | 6 |

Полные адреса и port_range: assets/sdr-deadlock.json. Приложение блокирует IPv4 и все протоколы только для deadlock.exe. Возможные IPv6 и непубличные маршруты не контролируются.

RU оставляет Стокгольм как приближение. EU исключает Стокгольм. Китай использует Гонконг. Это не фильтрация состава игроков.
