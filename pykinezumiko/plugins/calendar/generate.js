// node generate.js > chinese.txt
const format = new Intl.DateTimeFormat('zh-CN-u-ca-chinese', { dateStyle: 'full' })
const startDate = Date.UTC(1900, 0, 31)
const endDate = Date.UTC(2100, 11, 31)
for (let t = startDate; t <= endDate; t += 86400000) {
	const d = new Date(t)
	const s = format.format(d)
	if (s.includes('初一')) console.log(
		(d.toISOString().slice(0, 10) + s).replace(/[一-鿿]{2}年|初一|星期.|月/g, '')
		.replace(/闰?[正二三四五六七八九十一腊]{1,2}/, s =>
			('正二三四五六七八九十一腊'.indexOf(s.at(-1)) + 1) * (s.startsWith('闰') ? -1 : 1)
		)
	)
}
